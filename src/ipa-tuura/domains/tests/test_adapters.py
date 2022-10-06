from django.test import TestCase
from domains.adapters import DomainSerializer
from domains.tests.factories import DomainFactory



class DomainSerializerTest(TestCase):
    def test_model_fields(self):
        """Serializer data matches the Domain object for each field."""
        domain = DomainFactory()
        serializer = DomainSerializer(domain)

        for field_name in [
            'name', 'description', 'id_provider',
        ]:
            self.assertEqual(
                serializer.data[field_name],
                getattr(domain, field_name)
            )
