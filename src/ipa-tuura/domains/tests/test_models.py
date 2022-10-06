from django.test import TestCase

from domains.models import Domain
from domains.tests.factories import DomainFactory


class DomainTestCase(TestCase):
    def test_str(self):
        """Test for string representation."""
        domain = DomainFactory()
        self.assertEqual(str(domain), domain.name)
