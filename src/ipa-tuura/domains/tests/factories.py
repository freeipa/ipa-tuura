import random
import factory
from factory.django import DjangoModelFactory
from domains.models import Domain
from factory.faker import Faker

class DomainFactory(DjangoModelFactory):

    class Meta:
        model = Domain

    id = factory.Sequence(lambda n: n + 1)
    name = Faker('company')
    description = Faker('text')
    domain = Faker('url')
    # TODO implement custom factory faker provider
    id_provider = random.choice(["ipa", "ldap", "ad"])
