#
# Copyright (C) 2023  FreeIPA Contributors see COPYING for license
#

import logging
import os
import re
import socket
import subprocess
import tempfile

import ipalib.errors
import SSSDConfig
from ipalib import api
from ipalib.facts import is_ipa_client_configured
from scim.models import User

try:
    from ipalib.install.kinit import kinit_password
except ImportError:
    from ipapython.ipautil import kinit_password

try:
    import ConfigParser
except ImportError:
    import configparser as ConfigParser


logger = logging.getLogger(__name__)


def activate_ifp(domain):
    """
    Configure the ifp section of sssd.conf

    Activate the ifp service and add the following user_attributes
    to the [ifp] section:
    +mail, +givenname, +sn, +lock

    If the attributes were part of the negative list (for instance
    user_attributes = -givenname), they are removed from the negative list
    and added in the positive list.
    The other attributes are kept.
    """
    try:
        sssdconfig = SSSDConfig.SSSDConfig()
        sssdconfig.import_config()
    except Exception as e:
        logger.info("Unable to read SSSD config")
        raise e

    try:
        sssdconfig.new_service("ifp")
    except SSSDConfig.ServiceAlreadyExists:
        pass

    try:
        sssdconfig.activate_service("ifp")
        ifp = sssdconfig.get_service("ifp")
    except SSSDConfig.NoServiceError as e:
        logger.info("ifp service not enabled," "ensure the host is properly configured")
        raise e

    # edit the [ifp] section
    try:
        user_attrs = ifp.get_option("user_attributes")
    except SSSDConfig.NoOptionError:
        user_attrs = set()
    else:
        # TODO: read content from domain['user_extra_attrs']
        negative_set = {"-mail", "-givenname", "-sn", "-lock"}
        user_attrs = {
            s.strip()
            for s in user_attrs.split(",")
            if s.strip() and s.strip().lower() not in negative_set
        }

    positive_set = {"+mail", "+givenname", "+sn", "+lock"}
    ifp.set_option("user_attributes", ", ".join(user_attrs.union(positive_set)))
    # Workaround until we have rootless SSSD
    ifp.set_option("allowed_uids", "apache, sssd, root")

    sssdconfig.save_service(ifp)

    sssdconfig.write()


def install_client(domain):
    """
    :param domain
    """
    # test client_id and client_secret before

    args = [
        "sudo",
        "ipa-client-install",
        "--domain",
        domain["name"],
        "--realm",
        domain["name"].upper(),
        "-p",
        domain["client_id"],
        "-w",
        domain["client_secret"],
        "-U",
        "--force-join",
    ]

    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise Exception("Error enrolling client:\n{}".format(proc.stderr))
    else:
        # Install was successful, allow users in root group to access SSSD
        # config
        subprocess.run(["sudo", "chmod", "-R", "770", "/etc/sssd"])

    return proc


def uninstall_ipa_client():
    proc = subprocess.run(
        ["sudo", "ipa-client-install", "--uninstall", "-U"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise Exception("Error uninstalling client:\n{}".format(proc.stderr))

    return proc


def restart_sssd():
    args = ["sudo", "systemctl", "restart", "sssd"]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise Exception("Error restarting SSSD:\n{}".format(proc.stderr))


def ipa_api_connect(domain):
    backend = None
    context = "client"
    ccache_dir = tempfile.mkdtemp(prefix="krbcc")
    ccache_name = os.path.join(ccache_dir, "ccache")

    base_config = dict(context=context, in_server=False, debug=False)

    # kinit with user
    try:
        kinit_password(domain["client_id"], domain["client_secret"], ccache_name)
    except RuntimeError as e:
        raise RuntimeError("Kerberos authentication failed: {}".format(e))

    os.environ["KRB5CCNAME"] = ccache_name

    # init IPA API
    try:
        api.bootstrap(**base_config)
        if not api.isdone("finalize"):
            api.finalize()
    except Exception as e:
        logger.info(f"bootstrap already done {e}")

    backend = api.Backend.rpcclient
    if not backend.isconnected():
        backend.connect(ccache=os.environ.get("KRB5CCNAME", None))


def undeploy_ipa_service(domain):
    hostname = socket.gethostname()
    realm = domain["name"].upper()
    ipatuura_principal = "ipatuura/%s@%s" % (hostname, realm)
    keytab_file = os.environ.get("KRB5_CLIENT_KTNAME", None)
    ipa_api_connect(domain)

    # remove keytab
    args = ["ipa-rmkeytab", "-p", ipatuura_principal, "-k", keytab_file]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.info(f"Error rmkeytab: {proc.stderr}")

    # remove role member
    try:
        result = api.Command["role_remove_member"](
            cn="ipatuura writable interface", service=ipatuura_principal
        )
    except ipalib.errors.NotFound:
        logger.info("role member %s does not exist", ipatuura_principal)
        pass
    else:
        logger.info(f"ipa: role_remove_member result {result}")

    # delete role
    try:
        result = api.Command["role_del"](cn="ipatuura writable interface")
    except ipalib.errors.NotFound:
        logger.info("role %s does not exist", "ipatuura writable interface")
        pass
    else:
        logger.info(f"ipa: role_del result {result}")

    # delete service
    try:
        result = api.Command["service_del"](krbcanonicalname=ipatuura_principal)
    except ipalib.errors.NotFound:
        logger.info("service %s does not exist", ipatuura_principal)
        pass
    else:
        logger.info(f"ipa: service_del result {result}")


def deploy_ipa_service(domain):
    hostname = socket.gethostname()
    realm = domain["name"].upper()
    ipatuura_principal = "ipatuura/%s@%s" % (hostname, realm)
    keytab_file = os.environ.get("KRB5_CLIENT_KTNAME", None)
    keytab_path = os.path.dirname(keytab_file)

    ipa_api_connect(domain)

    # add extra attribute mappings to domain
    try:
        sssdconfig = SSSDConfig.SSSDConfig()
        sssdconfig.import_config()
    except Exception as e:
        logger.info("Unable to read SSSD config")
        raise e

    domainconfig = sssdconfig.get_domain(domain["name"])
    try:
        user_attrs = domainconfig.get_option("ldap_user_extra_attrs")
    except SSSDConfig.NoOptionError:
        user_attrs = set()
    else:
        user_attrs = {s.strip().lower() for s in user_attrs.split(",") if s.strip()}
    extra_attrs = {
        "mail:mail",
        "sn:sn",
        "givenname:givenname",
    }
    domainconfig.set_option(
        "ldap_user_extra_attrs", ", ".join(user_attrs.union(extra_attrs))
    )
    sssdconfig.save_domain(domainconfig)
    sssdconfig.write()

    subprocess.run(["sudo", "mkdir", "-m", "770", "-p", keytab_path])

    # add service
    try:
        result = api.Command["service_add"](krbcanonicalname=ipatuura_principal)
    except ipalib.errors.DuplicateEntry:
        logger.info("service %s already exists", ipatuura_principal)
        pass
    else:
        logger.info(f"ipa: service_add result {result}")

    # add role
    try:
        result = api.Command["role_add"](cn="ipatuura writable interface")
    except ipalib.errors.DuplicateEntry:
        logger.info("role %s already exists", "ipatuura writable interface")
        pass
    else:
        logger.info(f"ipa: role_add result {result}")

    # add role member
    try:
        result = api.Command["role_add_member"](
            cn="ipatuura writable interface", service=ipatuura_principal
        )
    except ipalib.errors.DuplicateEntry:
        logger.info("role member %s already exists", ipatuura_principal)
        pass
    else:
        logger.info(f"ipa: role_member_add result {result}")

    # add privileges to the role member
    try:
        result = api.Command["role_add_privilege"](
            cn="ipatuura writable interface", privilege="User Administrators"
        )
    except ipalib.errors.DuplicateEntry:
        logger.info("role member %s already exists", ipatuura_principal)
        pass
    else:
        logger.info(f"ipa: role_member_add result {result}")

    # get keytab
    args = ["ipa-getkeytab", "-p", ipatuura_principal, "-k", keytab_file]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise Exception("Error getkeytab:\n{}".format(proc.stderr))


def remove_sssd_domain(domain):
    try:
        sssdconfig = SSSDConfig.SSSDConfig()
        sssdconfig.import_config()
        domains = sssdconfig.list_active_domains()

        domain_name = None

        for name in domains:
            if name == domain["name"]:
                domain_name = name
                break

        if domain_name is not None:
            sssdconfig.delete_domain(domain_name)
            sssdconfig.write()
        else:
            logger.info(
                "IPA domain could not be found in /etc/sssd/sssd.conf "
                " and therefore not deleted"
            )
    except IOError:
        logger.info(
            "IPA domain could not be deleted. "
            "No access to the /etc/sssd/sssd.conf file."
        )


def join_ad_realm(domain):
    """
    Setup for creating default configuration file sssd.conf
    :param obj domain: integration domain object
    :Return: None
    """
    # pre-processing of the domain's payload
    realm = re.sub(r"ldap?://", "", domain["integration_domain_url"])
    args = ["realm", "discover", realm]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.info(f"Error realm discover: {proc.stderr}")
        raise Exception("Error realm discover:\n{}".format(proc.stderr))

    args = ["sudo", "realm", "join", realm]
    proc = subprocess.run(
        args, input=domain["client_secret"], capture_output=True, text=True
    )
    if proc.returncode != 0:
        logger.info(f"Error realm join: {proc.stderr}")
        raise Exception("Error realm join:\n{}".format(proc.stderr))

    # workaround until we have rootless SSSD
    subprocess.run(["sudo", "chmod", "660", "/etc/sssd/sssd.conf"])

    # add extra attribute mappings to domain
    try:
        sssdconfig = SSSDConfig.SSSDConfig()
        sssdconfig.import_config()
    except Exception as e:
        logger.info("Unable to read SSSD config")
        raise e

    domainconfig = sssdconfig.get_domain(domain["name"])
    try:
        user_attrs = domainconfig.get_option("ldap_user_extra_attrs")
    except SSSDConfig.NoOptionError:
        user_attrs = set()
    else:
        user_attrs = {s.strip().lower() for s in user_attrs.split(",") if s.strip()}
    extra_attrs = {
        "mail:mail",
        "sn:sn",
        "givenname:givenname",
    }
    domainconfig.set_option(
        "ldap_user_extra_attrs", ", ".join(user_attrs.union(extra_attrs))
    )
    sssdconfig.save_domain(domainconfig)
    sssdconfig.write()

    # workaround until we have rootless SSSD
    subprocess.run(["sudo", "chmod", "660", "/etc/sssd/sssd.conf"])


def config_default_sssd(domain):
    """
    Setup for creating default configuration file sssd.conf
    :param obj domain: integration domain object
    :Return: None
    """
    # pre-processing of the domain's payload
    suffix = domain["name"].split(".")
    domainname = domain["name"]
    id_provider = domain["id_provider"]
    ldap_uri = domain["integration_domain_url"]
    try:
        ldap_user_extra_attrs = (
            domain["user_extra_attrs"] + "mail:mail, sn:sn, givenname:givenname"
        )
    except KeyError:
        ldap_user_extra_attrs = "mail:mail, sn:sn, givenname:givenname"

    cfg = "/etc/sssd/sssd.conf"
    sssdconfig = ConfigParser.RawConfigParser()
    sssdconfig.optionxform = str

    sssdconfig.add_section("sssd")
    sssdconfig.set("sssd", "config_file_version", "2")
    sssdconfig.set("sssd", "domains", domainname)
    sssdconfig.set("sssd", "services", "nss, pam, ifp")
    domain_section = "%s/%s" % ("domain", domainname)
    sssdconfig.add_section(domain_section)
    sssdconfig.set(
        domain_section, "ldap_search_base", "dc=" + suffix[0] + ", dc=" + suffix[1]
    )
    sssdconfig.set(domain_section, "debug_level", "9")
    sssdconfig.set(domain_section, "id_provider", id_provider)
    sssdconfig.set(domain_section, "auth_provider", id_provider)
    sssdconfig.set(domain_section, "ldap_user_home_directory", "/home/%u")
    sssdconfig.set(domain_section, "ldap_uri", ldap_uri)
    sssdconfig.set(domain_section, "ldap_user_extra_attrs", ldap_user_extra_attrs)
    sssdconfig.set(domain_section, "ldap_default_bind_dn", domain["client_id"])
    sssdconfig.set(domain_section, "ldap_default_authtok", domain["client_secret"])
    sssdconfig.set(domain_section, "use_fully_qualified_names", "True")
    sssdconfig.set(domain_section, "cache_credentials", "True")
    sssdconfig.set(domain_section, "enumerate", "True")
    sssdconfig.set(domain_section, "timeout", "60")
    sssdconfig.add_section("nss")
    sssdconfig.set("nss", "timeout", "60")
    sssdconfig.add_section("pam")
    sssdconfig.set("pam", "timeout", "60")
    sssdconfig.add_section("ifp")

    # TODO process ldap_tls_cacert, base64decode.
    cert_location = "/etc/openldap/certs/cacert.pem"
    sssdconfig.set(domain_section, "ldap_tls_cacert", cert_location)

    with open(cfg, "w") as fd:
        subprocess.run(["sudo", "chmod", "660", cfg])
        subprocess.run(["sudo", "chown", "root:root", cfg])
        sssdconfig.write(fd)


# CRUD functions
def add_domain(domain):
    """
    Add an integration domain with extra attribute mappings

    Supported identity providers: ipa, ldap, and ad.
    """
    # Fail is there's a domain already registered
    try:
        sssdconfig = SSSDConfig.SSSDConfig()
        sssdconfig.import_config()
        domains = sssdconfig.list_active_domains()
    except Exception:
        # SSSD doesn't exist
        domains = []
    if len(domains) > 0:
        raise RuntimeError(
            "An existing integration domain is already enabled, "
            "please delete it before adding a new one."
        )

    # IPA: enroll ipa-tuura as an IPA client to the domain
    # LDAP: add default ldap sssd.conf
    if domain["id_provider"] == "ipa":
        if is_ipa_client_configured():
            undeploy_ipa_service(domain)
            uninstall_ipa_client()
        install_client(domain)
        deploy_ipa_service(domain)
    elif domain["id_provider"] == "ad":
        join_ad_realm(domain)
    else:
        config_default_sssd(domain)

    # activate infopipe attrs and restart sssd service
    activate_ifp(domain)
    # TODO: as a workaround until rootless SSSD is available,
    # change permissions for sssd.conf to 600, restart and return
    # to 660
    subprocess.run(["sudo", "chmod", "600", "/etc/sssd/sssd.conf"])
    restart_sssd()
    subprocess.run(["sudo", "chmod", "660", "/etc/sssd/sssd.conf"])


def delete_domain(domain):
    """
    Delete an integration domain
    """
    if domain["id_provider"] == "ipa":
        # undeploy the service account
        undeploy_ipa_service(domain)

        # ipa client uninstall moves the sssd.conf to sssd.conf.deleted
        uninstall_ipa_client()
    else:
        # LDAP (ad, ldap): remove domain from sssd.conf
        # TODO: undeploy LDAP service account
        remove_sssd_domain(domain)

    # Delete all registered users except superuser
    User.objects.exclude(scim_username="scim").delete()
