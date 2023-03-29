#
# Copyright (C) 2022  FreeIPA Contributors see COPYING for license
#

#!/bin/python3
import subprocess
import sys

import SSSDConfig


def activate_ifp(sssdconfig):
    """
    Configure the ifp section of sssd.conf

    Add, then activate the ifp service and add the following user_attributes
    to the [ifp] section:
    +mail, +givenname, +sn, +lock

    If the attributes were part of the negative list (for instance
    user_attributes = -givenname), they are removed from the negative list
    and added in the positive list.
    The other attributes are kept.
    """

    try:
        sssdconfig.new_service("ifp")
    except SSSDConfig.ServiceAlreadyExists:
        pass
    except Exception as e:
        print("Unable to add ifp section to SSSD Configuration")
        raise e

    try:
        sssdconfig.activate_service("ifp")
        ifp = sssdconfig.get_service("ifp")
    except SSSDConfig.NoServiceError as e:
        print("ifp service not enabled, " "ensure the host is properly configured")
        raise e

    # edit the [ifp] section
    try:
        user_attrs = ifp.get_option("user_attributes")
    except SSSDConfig.NoOptionError:
        user_attrs = set()
    else:
        negative_set = {"-mail", "-givenname", "-sn", "-lock"}
        user_attrs = {
            s.strip()
            for s in user_attrs.split(",")
            if s.strip() and s.strip().lower() not in negative_set
        }

    positive_set = {"+mail", "+givenname", "+sn", "+lock"}
    ifp.set_option("user_attributes", ", ".join(user_attrs.union(positive_set)))
    sssdconfig.save_service(ifp)


def configure_domain(domain):
    """
    Configure the domain with extra attribute mappings

    Add the following ldap_user_extra_attrs mappings to the [domain/<name>]
    section:
    mail:mail, sn:sn, givenname:givenname
    If the section already defines some mappings, they are kept.
    """
    try:
        extra_attrs = domain.get_option("ldap_user_extra_attrs")
    except SSSDConfig.NoOptionError:
        extra_attrs = set()
    else:
        extra_attrs = {s.strip().lower() for s in extra_attrs.split(",") if s.strip()}

    additional_attrs = {
        "mail:mail",
        "sn:sn",
        "givenname:givenname",
        "lock:nsaccountlock",
    }
    domain.set_option(
        "ldap_user_extra_attrs", ", ".join(extra_attrs.union(additional_attrs))
    )


def configure_domains(sssdconfig):
    """
    Configure the domains with extra attribute mappings

    Loop on the configured domains and configure the domain with extra
    attribute mappings if the id_provider is one of "ipa", "ad", "ldap".
    """
    # Configure each ipa/ad/ldap domain
    domains = sssdconfig.list_active_domains()
    for name in domains:
        domain = sssdconfig.get_domain(name)
        provider = domain.get_option("id_provider")
        if provider in {"ipa", "ad", "ldap"}:
            configure_domain(domain)
            sssdconfig.save_domain(domain)


def main():
    try:
        sssdconfig = SSSDConfig.SSSDConfig()
        sssdconfig.import_config()
    except Exception as e:
        # SSSD configuration does not exist or cannot be parsed
        print("Unable to parse SSSD configuration")
        print("Please ensure the host is properly configured.")
        raise e

    # Ensure ifp service is enabled
    # Add attributes to the InfoPipe responder
    activate_ifp(sssdconfig)

    # Add attributes to the domain section
    configure_domains(sssdconfig)

    sssdconfig.write()

    # Restart SSSD
    args = ["systemctl", "restart", "sssd"]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise Exception("Error restarting SSSD:\n{}".format(proc.stderr))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(e)
