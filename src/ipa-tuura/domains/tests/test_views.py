import factory
from django.test import TestCase
from django.urls import reverse
from domains.tests.factories import DomainFactory
from rest_framework import status


class DomainViewSetTestCase(TestCase):
    @classmethod
    def setUp(self):
        self.domain = DomainFactory._meta.model

    def get_detail_url(self, domain_id):
        return reverse(self.domain.detail, kwargs={"id": domain_id})

    def test_get_list(self):
        """GET the list of Domains"""
        domain = DomainFactory.create(name="unit.test")
        response = self.client.get(reverse("domain-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(domain.name, str(response.data))

    def test_post(self):
        """POST to create a Domain."""
        data = {
            "name": "ldap.test",
            "description": "LDAP Integration Domain",
            "integration_domain_url": "ldap://rhds.ldap.test",
            "client_id": "cn=Directory Manager",
            "client_secret": "Secret123",
            "id_provider": "ldap",
            "user_extra_attrs": "mail:mail, sn:sn, givenname:givenname",
            "user_object_classes": "inetOrgPerson,organizationalPerson,person,top",
            "users_dn": "ou=people,dc=ldap,dc=test",
            "ldap_tls_cacert": "/etc/openldap/certs/cacert.pem",
        }
        self.assertEqual(self.domain.objects.count(), 0)
        response = self.client.post(reverse("domain-list"), data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.domain.objects.count(), 1)
        domain = self.domain.objects.all().first()
        for field_name in data.keys():
            self.assertEqual(getattr(domain, field_name), data[field_name])

    def test_delete(self):
        domain = DomainFactory.create(name="delete.test")
        response = self.client.delete(reverse("domain-list") + str(domain.id))
        print(response)
        self.assertEqual(response.status_code, status.HTTP_301_MOVED_PERMANENTLY)
