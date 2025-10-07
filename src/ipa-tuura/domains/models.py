#
# Copyright (C) 2024  FreeIPA Contributors see COPYING for license
#

import logging

from django.db import models
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


class Domain(models.Model):
    """
    Integration Domain model.
    This defines an integration domain supported by ipatuura service.
    The fields corresponds to the integration domain required
    and optional configuration fields.
    """

    class DomainProviderType(models.TextChoices):
        """
        Field Choices for the supported integration domain provider types
        """

        IPA = "ipa", _("IPA Provider")
        AD = "ad", _("LDAP Active Directory Provider")
        LDAP = "ldap", _("LDAP Provider")

    # TODO: multi-domain, implement is_active boolean flag
    # it designates whether the integration domain should be considered active
    # is_active = models.BooleanField(verbose_name='is active?', default=True)

    # Domain Name
    name = models.CharField(max_length=80)

    # Optional description
    description = models.TextField(blank=True)

    # The connection URL to the identity server
    integration_domain_url = models.CharField(max_length=255)

    # Temporary admin service username
    client_id = models.CharField(max_length=255)

    # Temporary admin service password
    client_secret = models.CharField(max_length=20)

    # External hostname for Keycloak host
    keycloak_hostname = models.CharField(max_length=255, blank=True)

    # Identity provider type
    id_provider = models.CharField(
        max_length=5,
        choices=DomainProviderType.choices,
        default=DomainProviderType.IPA,
    )

    # Optional comma-separated list of extra attributes to download
    # along with the user entry
    user_extra_attrs = models.CharField(max_length=255, blank=True)

    # Optional user object classes
    user_object_classes = models.CharField(max_length=255, blank=True)

    # Optional full DN of LDAP tree where users are
    users_dn = models.CharField(max_length=255)

    # LDAP auth with TLS support, the file path for now
    # TODO: base64 decode CA cert from HTTP request
    ldap_tls_cacert = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.name

    # This should be implemented in the keycloak plugin input validation
    # enforce defaults based on other fields
    def save(self, *args, **kwargs):
        # logic for default vaules part of simplification process
        if not self.user_extra_attrs:
            self.user_extra_attrs = "mail:mail, sn:sn, givenname:givenname"

        if self.id_provider == "ldap":
            if not self.user_object_classes:
                self.user_object_classes = (
                    "inetOrgPerson," "organizationalPerson," "person," "top"
                )
            # This will be overwritten by AD/IPA providers with realm join
            if not self.ldap_tls_cacert:
                self.ldap_tls_cacert = "/etc/openldap/certs/cacert.pem"

        elif self.id_provider == "ad":
            if not self.user_object_classes:
                self.user_object_classes = (
                    "user," "organizationalPerson," "person," "top"
                )

        # We should only have one domain registered, override primary key
        # so that the Domain class acts as a singleton
        self.pk = 1

        super().save(*args, **kwargs)
