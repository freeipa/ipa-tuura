#
# Copyright (C) 2022  FreeIPA Contributors see COPYING for license
#

import datetime
import logging
import os
import uuid
from decimal import Decimal

import domains
import gssapi
import ldap
import ldap.modlist as modlist
import six
from cryptography import x509 as crypto_x509
from cryptography.hazmat.primitives import serialization as x509
from ipalib import api
from ipalib.errors import EmptyModlist
from ipalib.facts import is_ipa_client_configured
from ipalib.install.kinit import kinit_keytab
from ipalib.krb_utils import get_credentials_if_valid
from ipapython import admintool
from ipapython.dn import DN
from ipapython.dnsutil import DNSName
from ipapython.kerberos import Principal

if six.PY3:
    unicode = str


logger = logging.getLogger(__name__)


LDAP_GENERALIZED_TIME_FORMAT = "%Y%m%d%H%M%SZ"


class LDAPNotFoundException(Exception):
    """
    Exception returned when an LDAP user or group is not found.
    """

    pass


class IPANotFoundException(Exception):
    """
    Exception returned when an IPA user or group is not found.
    """

    pass


class IPAAPI(admintool.AdminTool):
    """
    Initialization of the IPA API writable interface
    """

    def __init__(self):
        """
        Initialize IPA API.
        Set IPA API execution client context
        """
        if not is_ipa_client_configured():
            logger.error("IPA client is not configured on this system.")
            raise admintool.ScriptError()

        self._conn = None
        self._backend = None
        self._context = "client"
        self._ccache_dir = None
        self._ccache_name = None
        self._ipa_connect()

    def _ipa_connect(self):
        """
        Initialize IPA API
        """
        base_config = dict(context=self._context, in_server=False, debug=False)
        try:
            self._valid_creds()
        except Exception as e:
            logger.error(f"Failed to find default ccache {e}")

        try:
            api.bootstrap(**base_config)
            if not api.isdone("finalize"):
                api.finalize()
        except Exception as e:
            logger.info(f"bootstrap already done {e}")

        self._backend = api.Backend.rpcclient
        if not self._backend.isconnected():
            self._backend.connect(ccache=os.environ.get("KRB5CCNAME", None))

    def _valid_creds(self):
        # try GSSAPI first
        if "KRB5CCNAME" in os.environ:
            ccache = os.environ["KRB5CCNAME"]
            logger.info(f"ipa: init KRB5CCNAME set to {ccache}")

            try:
                cred = gssapi.Credentials(usage="initiate", store={"ccache": ccache})
            except gssapi.raw.misc.GSSError as e:
                logger.error(f"Failed to find default ccache {e}")
            else:
                logger.info(f"Using principal {cred.name}")
                return True

        # KRB5_CLIENT_KTNAME os env is defined in settings.py
        elif "KRB5_CLIENT_KTNAME" in os.environ:
            keytab = os.environ.get("KRB5_CLIENT_KTNAME", None)
            logger.info(f"KRB5_CLIENT_KTNAME set to {keytab}")
            ccache_name = "MEMORY:%s" % str(uuid.uuid4())
            os.environ["KRB5CCNAME"] = ccache_name

            try:
                logger.info("kinit keytab")
                cred = kinit_keytab(
                    domains.models.Domain.objects.last().client_id, keytab, ccache_name
                )
            except gssapi.raw.misc.GSSError as e:
                logger.error(f"Kerberos authentication failed {e}")
            else:
                logger.info(f"Using principal {cred.name}")
                return True

        creds = get_credentials_if_valid()
        if (
            creds
            and creds.lifetime > 0
            and "%s@" % domains.models.Domain.objects.last().client_id
            in creds.name.display_as(creds.name.name_type)
        ):
            return True
        return False

    def add(self, scim_user):
        """
        Add a new user

        :param scim_user: user object conforming to the SCIM User Schema
        """
        self._ipa_connect()
        result = api.Command["user_add"](
            uid=scim_user.obj.username,
            givenname=scim_user.obj.first_name,
            sn=scim_user.obj.last_name,
            mail=scim_user.obj.email,
        )
        logger.info(f"ipa user_add result {result}")

    def modify(self, scim_user):
        """
        Modify user

        :param scim_user: user object conforming to the SCIM User Schema
        :raises IPANotFoundException: if no user matching the username exists
        """
        self._ipa_connect()
        try:
            result = api.Command["user_mod"](
                scim_user.obj.username,
                givenname=scim_user.obj.first_name,
                sn=scim_user.obj.last_name,
                mail=scim_user.obj.email,
            )
        except EmptyModlist:
            logger.debug("No modification for user {}".format(scim_user.obj.username))
            return
        except Exception:
            raise IPANotFoundException(
                "User {} not found".format(scim_user.obj.username)
            )
        logger.info(f"ipa: user_mod result {result}")

    def delete(self, scim_user):
        """
        Delete user

        :param scim_user: user object conforming to the SCIM User Schema
        :raises IPANotFoundException: if no user matching the username exists
        """
        self._ipa_connect()
        try:
            result = api.Command["user_del"](uid=scim_user.obj.username)
        except Exception:
            raise IPANotFoundException(
                "User {} not found".format(scim_user.obj.username)
            )
        logger.info(f"ipa: user_del result {result}")


class LDAP:
    """
    Initialization of the LDAP writable interface
    """

    def __init__(self):
        self._conn = None
        self._dn = None
        self._users_dn = None
        self._ldap_uri = None
        self._ldap_user_extra_attrs = None
        self._user_object_classes = None
        # TLS
        self._ldap_tls_cacert = None
        self._sasl_gssapi = ldap.sasl.sasl({}, "GSSAPI")
        self._client_id = None
        self._client_secret = None
        # init and connect
        self._fetch_domain()
        self._conn = self._bind()
        self._user_rdn_attr = "uid"

    def _fetch_domain(self):
        """
        Fetch relevant information from the integration domain
        """
        domain = domains.models.Domain.objects.last()
        suffix = domain.name.split(".")

        self._dn = domain.client_id
        self._ldap_uri = domain.integration_domain_url
        self._ldap_user_extra_attrs = domain.user_extra_attrs
        self._ldap_tls_cacert = domain.ldap_tls_cacert
        self._client_id = domain.client_id
        self._client_secret = domain.client_secret
        self._users_dn = domain.users_dn
        self._user_object_classes = [
            x.strip() for x in domain.user_object_classes.split(",")
        ]

        logger.info(f"Domain info: {domain}")

    def _bind(self):
        """
        Bind to ldap server
        """
        self._fetch_domain()
        # TODO enable TLS support
        # self._conn = ldap.initialize(self._ldap_uri)
        # self._conn.set_option(ldap.OPT_X_TLS_CACERTFILE, self._tls_cacert)
        # self._conn.sasl_interactive_bind_s('', self._sasl_gssapi)
        self._conn = ldap.initialize(self._ldap_uri)
        self._conn.protocol_version = 3
        self._conn.set_option(ldap.OPT_REFERRALS, 0)
        try:
            self._conn.simple_bind_s(self._dn, self._client_secret)
        except Exception as e:
            logger.error(f"Unable to bind to LDAP server {e}")
        else:
            return self._conn

    def encode(self, val):
        """
        Encode attribute value to LDAP representation (str/bytes)
        """
        # Booleans are both an instance of bool and int, therefore
        # test for bool before int otherwise the int clause will be
        # entered for a boolean value instead of the boolean clause.
        if isinstance(val, bool):
            if val:
                return b"TRUE"
            else:
                return b"FALSE"
        elif isinstance(val, (unicode, int, Decimal, DN, Principal)):
            return str(val).encode("utf-8")
        elif isinstance(val, DNSName):
            return val.to_text().encode("ascii")
        elif isinstance(val, bytes):
            return val
        elif isinstance(val, list):
            return [self.encode(m) for m in val]
        elif isinstance(val, tuple):
            return tuple(self.encode(m) for m in val)
        elif isinstance(val, dict):
            # key in dict must be str not bytes
            dct = dict((k, self.encode(v)) for k, v in val.items())
            return dct
        elif isinstance(val, datetime.datetime):
            return val.strftime(LDAP_GENERALIZED_TIME_FORMAT).encode("utf-8")
        elif isinstance(val, crypto_x509.Certificate):
            return val.public_bytes(x509.Encoding.DER)
        elif val is None:
            return None
        else:
            raise TypeError(
                "attempt to pass unsupported type to ldap, "
                "value=%s type=%s" % (val, type(val))
            )

    def add(self, scim_user):
        """
        Add a new user

        :param scim_user: user object conforming to the SCIM User Schema
        For a RHDS deployment:
        dc=ipa,dc=com
          cn=accounts
            cn=users
              uid=oneuser
        """
        # TODO: implement dynamic list based on _ldap_user_extra_attrs
        attrs = {}
        attrs["cn"] = self.encode(scim_user.obj.username)
        attrs["sn"] = self.encode(scim_user.obj.last_name)
        attrs["givenname"] = self.encode(scim_user.obj.first_name)
        attrs["mail"] = self.encode(scim_user.obj.email)
        attrs["objectClass"] = self.encode(self._user_object_classes)
        ldif = modlist.addModlist(attrs)

        self._bind()
        try:
            # AD: cn, LDAP: uid
            self._conn.add_s(
                "{rdnattr}={rdnval},{usersdn}".format(
                    rdnattr=self._user_rdn_attr,
                    rdnval=scim_user.obj.username,
                    usersdn=self._users_dn,
                ),
                ldif,
            )
        except ldap.LDAPError as e:
            desc = e.args[0]["desc"].strip()
            info = e.args[0].get("info", "").strip()
            logger.error(f"LDAP Error: {desc}: {info}")

    def modify(self, scim_user):
        """
        Modify user

        :param scim_user: user object conforming to the SCIM User Schema
        """
        dn = "{rdnattr}={rdnval},{usersdn}".format(
            rdnattr=self._user_rdn_attr,
            rdnval=scim_user.obj.username,
            usersdn=self._users_dn,
        )

        sn = self.encode(scim_user.obj.last_name)
        givenname = self.encode(scim_user.obj.first_name)
        mail = self.encode(scim_user.obj.email)

        mod_attrs = [
            (ldap.MOD_REPLACE, "sn", sn),
            (ldap.MOD_REPLACE, "givenname", givenname),
            (ldap.MOD_REPLACE, "mail", mail),
        ]

        self._bind()
        try:
            self._conn.modify_ext_s(dn, mod_attrs)
        except ldap.TYPE_OR_VALUE_EXISTS:
            pass
        except ldap.NO_SUCH_OBJECT:
            raise LDAPNotFoundException(
                "User {} not found".format(scim_user.obj.username)
            )

    def delete(self, scim_user):
        """
        Delete user

        :param scim_user: user object conforming to the SCIM User Schema
        """
        self._bind()
        try:
            self._conn.delete_s(
                "{rdnattr}={rdnval},{usersdn}".format(
                    rdnattr=self._user_rdn_attr,
                    rdnval=scim_user.obj.username,
                    usersdn=self._users_dn,
                )
            )
        except ldap.LDAPError as e:
            desc = e.args[0]["desc"].strip()
            info = e.args[0].get("info", "").strip()
            logger.error(f"LDAP Error: {desc}: {info}")


class AD(LDAP):
    """
    Initialization of the LDAP AD writable interface
    """

    def __init__(self):
        super().__init__()
        self._user_rdn_attr = "cn"


class _IPA:
    _instance = None

    def __init__(self):
        """
        Initialize writable interface
        """
        self._apiconn = self._write(domains.models.Domain.objects.last().id_provider)

    def _write(self, iface="ipa"):
        """
        Factory Method
        """
        ifaces = {
            "ipa": IPAAPI,
            "ldap": LDAP,
            "ad": AD,
        }
        return ifaces[iface]()

    # CRUD Operations
    def user_add(self, scim_user):
        self._apiconn.add(scim_user)

    def user_mod(self, scim_user):
        self._apiconn.modify(scim_user)

    def user_del(self, scim_user):
        self._apiconn.delete(scim_user)


def IPA():
    if _IPA._instance is None:
        _IPA._instance = _IPA()
    return _IPA._instance
