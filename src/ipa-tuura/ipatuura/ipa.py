#
# Copyright (C) 2022  FreeIPA Contributors see COPYING for license
#

import logging
import os
import gssapi
import uuid
import six
import ldap
import ldap.modlist as modlist
import SSSDConfig
import datetime

from django.conf import settings
from ipalib.krb_utils import get_credentials_if_valid
from ipalib import api
from ipalib.errors import EmptyModlist
from ipalib.facts import is_ipa_client_configured
from ipalib.install.kinit import kinit_keytab
from ipapython import admintool
from ipapython.dn import DN
from ipapython.dnsutil import DNSName
from ipapython.kerberos import Principal
from decimal import Decimal
from cryptography import x509 as crypto_x509
from cryptography.hazmat.primitives import serialization as x509

if six.PY3:
    unicode = str


logger = logging.getLogger(__name__)


LDAP_GENERALIZED_TIME_FORMAT = "%Y%m%d%H%M%SZ"


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
        base_config = dict(
            context=self._context, in_server=False, debug=False
        )
        try:
            self._valid_creds()
        except Exception as e:
            logger.error(f'Failed to find default ccache {e}')

        try:
            api.bootstrap(**base_config)
            if not api.isdone("finalize"):
                api.finalize()
        except Exception as e:
            logger.info(f'bootstrap already done {e}')

        self._backend = api.Backend.rpcclient
        if not self._backend.isconnected():
            self._backend.connect(ccache=os.environ.get('KRB5CCNAME', None))

    def _valid_creds(self):
        # try GSSAPI first
        logger.info('valid creds')
        if "KRB5CCNAME" in os.environ:
            ccache = os.environ["KRB5CCNAME"]
            logger.info(f'ipa: init KRB5CCNAME set to {ccache}')

            try:
                cred = gssapi.Credentials(usage='initiate',
                                          store={'ccache': ccache})
            except gssapi.raw.misc.GSSError as e:
                logger.error(f'Failed to find default ccache {e}')
            else:
                logger.info(f'Using principal {cred.name}')
                return True

        # KRB5_CLIENT_KTNAME os env is defined in settings.py
        elif "KRB5_CLIENT_KTNAME" in os.environ:
            logger.info('ktname')
            keytab = os.environ.get('KRB5_CLIENT_KTNAME', None)
            logger.info(f'KRB5_CLIENT_KTNAME set to {keytab}')
            ccache_name = "MEMORY:%s" % str(uuid.uuid4())
            os.environ["KRB5CCNAME"] = ccache_name

            try:
                logger.info('kinit keytab')
                cred = kinit_keytab(
                    settings.SCIM_SERVICE_PROVIDER['WRITABLE_USER'],
                    keytab,
                    ccache_name
                    )
            except gssapi.raw.misc.GSSError as e:
                logger.error(f'Kerberos authentication failed {e}')
            else:
                logger.info(f'Using principal {cred.name}')
                return True

        logger.info('get credentials if valid')
        creds = get_credentials_if_valid()
        if creds and \
           creds.lifetime > 0 and \
           "%s@" % settings.SCIM_SERVICE_PROVIDER['WRITABLE_USER'] in \
           creds.name.display_as(creds.name.name_type):
            return True
        return False

    def add(self, scim_user):
        """
        Add a new user

        :param scim_user: user object conforming to the SCIM User Schema
        """
        self._ipa_connect()
        result = api.Command['user_add'](
            uid=scim_user.obj.username,
            givenname=scim_user.obj.first_name,
            sn=scim_user.obj.last_name,
            mail=scim_user.obj.email
            )
        logger.info(f'ipa user_add result {result}')

    def modify(self, scim_user):
        """
        Modify user

        :param scim_user: user object conforming to the SCIM User Schema
        :raises IPANotFoundException: if no user matching the username exists
        """
        self._ipa_connect()
        try:
            result = api.Command['user_mod'](
                scim_user.obj.username,
                givenname=scim_user.obj.first_name,
                sn=scim_user.obj.last_name,
                mail=scim_user.obj.email
                )
        except EmptyModlist:
            logger.debug("No modification for user {}".format(
                scim_user.obj.username))
            return
        except Exception:
            raise IPANotFoundException(
                "User {} not found".format(scim_user.obj.username)
                )
        logger.info(f'ipa: user_mod result {result}')

    def delete(self, scim_user):
        """
        Delete user

        :param scim_user: user object conforming to the SCIM User Schema
        :raises IPANotFoundException: if no user matching the username exists
        """
        self._ipa_connect()
        try:
            result = api.Command['user_del'](
                uid=scim_user.obj.username
                )
        except Exception:
            raise IPANotFoundException(
                "User {} not found".format(scim_user.obj.username)
                )
        logger.info(f'ipa: user_del result {result}')


class LDAP:
    """
    Initialization of the LDAP writable interface
    """
    def __init__(self):
        self._conn = None
        self._users_dn = None
        self._ldap_uri = None
        self._ldap_search_base = None
        self._ldap_user_extra_attrs = None
        self._user_objectclass = None
        # TLS
        self._ldap_tls_cacert = None
        self._sasl_gssapi = ldap.sasl.sasl({}, 'GSSAPI')

        # read settings from sssd.conf file
        self._read_sssd_config()

        # TODO: these seetings are not available in sssd.conf file
        # hence they should be set from domains app
        # Red Hat Directory Server
        # users_dn 'cn=users,cn=accounts'
        # user_objectclass inetOrgPerson

        # Active Directory
        self._users_dn = 'CN=Users'
        self._user_objectclass = [
            b'user',
            b'organizationalPerson',
            b'person',
            b'top'
        ]
        self._ldap_connect()

    def _read_sssd_config(self):
        try:
            sssdconfig = SSSDConfig.SSSDConfig()
            sssdconfig.import_config()
        except Exception as e:
            # SSSD configuration does not exist or cannot be parsed
            print("Unable to parse SSSD configuration")
            print("Please ensure the host is properly configured.")
            raise e
        # Read attributes from the domain section
        self._read_ldap_domains(sssdconfig)

    # this function will be useful later on for multi-domains support
    def _read_ldap_domains(self, sssdconfig):
        """
        Read the domains with extra attribute mappings

        Loop on the configured domains and read the domain with extra
        attribute mappings if the id_provider is "ldap".
        """
        # Configure each ipa/ad/ldap domain
        domains = sssdconfig.list_active_domains()
        for name in domains:
            domain = sssdconfig.get_domain(name)
            provider = domain.get_option('id_provider')
            if provider in {"ldap"}:
                self._read_ldap_domain(domain)

    def _read_ldap_domain(self, domain):
        """
        Read the domain with extra attribute mappings from the [domain/<name>]
        section (default is mail:mail, sn:sn, givenname:givenname)

        ldap_uri, ldap_search_base, ldap_tls_cacert, ldap_user_extra_attrs
        """
        try:
            self._uri = domain.get_option('ldap_uri')
            self._base_dn = domain.get_option('ldap_search_base')
            self._tls_cacert = domain.get_option('ldap_tls_cacert')
            self._ldap_user_extra_attrs = domain.get_option(
                'ldap_user_extra_attrs')
        except Exception as e:
            # SSSD configuration does not exist or cannot be parsed
            print("Unable to parse SSSD configuration")
            print("Please ensure the host is properly configured.")
            raise e

    def _ldap_connect(self):
        """
        Create a connection to LDAP and bind to it.
        """
        # TODO enable TLS support
        try:
            self._conn = ldap.initialize(self._uri)
            self._conn.protocol_version = 3
            self._conn.set_option(ldap.OPT_REFERRALS, 0)
            self._conn.simple_bind_s('Administrator@da.test', 'Secret123')
        except Exception as e:
            logger.error(f'Unable to bind to LDAP AD server {e}')

    def encode(self, val):
        """
        Encode attribute value to LDAP representation (str/bytes)
        """
        # Booleans are both an instance of bool and int, therefore
        # test for bool before int otherwise the int clause will be
        # entered for a boolean value instead of the boolean clause.
        if isinstance(val, bool):
            if val:
                return b'TRUE'
            else:
                return b'FALSE'
        elif isinstance(val, (unicode, int, Decimal, DN, Principal)):
            return str(val).encode('utf-8')
        elif isinstance(val, DNSName):
            return val.to_text().encode('ascii')
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
            return val.strftime(LDAP_GENERALIZED_TIME_FORMAT).encode('utf-8')
        elif isinstance(val, crypto_x509.Certificate):
            return val.public_bytes(x509.Encoding.DER)
        elif val is None:
            return None
        else:
            raise TypeError("attempt to pass unsupported type to ldap, "
                            "value=%s type=%s" % (val, type(val)))

    def add(self, scim_user):
        """
        Add a new user

        :param scim_user: user object conforming to the SCIM User Schema

        For a RHDS deployment:
        dc=ipa,dc=com
          cn=accounts
            cn=users
              uid=oneuser
        For an AD deployment:
        dc=ad,dc=com
          cn=users
            cn=oneuser
        """
        attrs = {}
        attrs['objectclass'] = self._user_objectclass
        attrs['cn'] = self.encode(scim_user.obj.username)
        attrs['mail'] = self.encode(scim_user.obj.email)
        attrs['givenname'] = self.encode(scim_user.obj.first_name)
        attrs['sn'] = self.encode(scim_user.obj.last_name)
        ldif = modlist.addModlist(attrs)

        self._ldap_connect()
        try:
            # AD: cn, LDAP: uid
            self._conn.add_s("cn={uid},{usersdn},{basedn}".format(
                uid=scim_user.obj.username,
                usersdn=self._users_dn,
                basedn=self._base_dn), ldif)
        except ldap.LDAPError as e:
            desc = e.args[0]['desc'].strip()
            info = e.args[0].get('info', '').strip()
            logger.error(f'LDAP Error: {desc}: {info}')

    def modify(self, scim_user):
        """
        Modify user

        :param scim_user: user object conforming to the SCIM User Schema
        """
        attrs = {}
        attrs['objectclass'] = self._user_objectclass
        attrs['cn'] = self.encode(scim_user.obj.username)
        attrs['mail'] = self.encode(scim_user.obj.email)
        attrs['givenname'] = self.encode(scim_user.obj.first_name)
        attrs['sn'] = self.encode(scim_user.obj.last_name)
        ldif = modlist.addModlist(attrs)

        self._ldap_connect()
        try:
            self._conn.modify_s("cn={uid},{usersdn},{basedn}".format(
                uid=scim_user.obj.username,
                usersdn=self._users_dn,
                basedn=self._base_dn), ldif)
        except ldap.LDAPError as e:
            desc = e.args[0]['desc'].strip()
            info = e.args[0].get('info', '').strip()
            logger.error(f'LDAP Error: {desc}: {info}')

    def delete(self, scim_user):
        """
        Delete user

        :param scim_user: user object conforming to the SCIM User Schema
        """
        self._ldap_connect()
        try:
            self._conn.delete_s("cn={uid},{usersdn},{basedn}".format(
                uid=scim_user.obj.username,
                usersdn=self._users_dn,
                basedn=self._base_dn))
        except ldap.LDAPError as e:
            desc = e.args[0]['desc'].strip()
            info = e.args[0].get('info', '').strip()
            logger.error(f'LDAP Error: {desc}: {info}')


class _IPA():
    _instance = None

    def __init__(self):
        """
        Initialize writable interface
        Instantiate the writable interface depending on the current
        configuration settings.py: SCIM_SERVICE_PROVIDER['WRITABLE_IFACE']
        """
        self._apiconn = self._write(
            settings.SCIM_SERVICE_PROVIDER['WRITABLE_IFACE']
        )

    def _write(self, iface="ipa"):
        """
        Factory Method
        """
        ifaces = {
            "ipa": IPAAPI,
            "ldap": LDAP,
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
