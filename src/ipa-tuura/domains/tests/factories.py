from domains.models import Domain
from factory.django import DjangoModelFactory


class DomainFactory(DjangoModelFactory):
    name = "ipa.test"
    description = "IPA Integration Domain"
    integration_domain_url = "https://master.ipa.test"
    client_id = "admin"
    client_secret = "Secret123"
    id_provider = "ipa"
    user_extra_attrs = "mail:mail, sn:sn, givenname:givenname"
    user_object_classes = ""
    users_dn = "ou=people,dc=ldap,dc=test"
    ldap_tls_cacert = "/etc/openldap/certs/cacert.pem"

    class Meta:
        model = Domain
        django_get_or_create = ("name",)
