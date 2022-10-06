from django.test import TestCase
from domains.adapters import DomainSerializer
from domains.tests.factories import DomainFactory


class DomainSerializerTestCase(TestCase):
    def test_model_fields(self):
        """Serializer data matches the Domain object for each field."""
        domain = DomainFactory()
        serializer = DomainSerializer(domain)
        for field_name in [
            "id",
            "name",
            "description",
            "integration_domain_url",
            "client_id",
            "client_secret",
            "id_provider",
            "user_extra_attrs",
            "user_object_classes",
            "users_dn",
            "ldap_tls_cacert",
        ]:
            self.assertEqual(serializer.data[field_name], getattr(domain, field_name))
