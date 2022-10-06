import logging

from rest_framework.serializers import ModelSerializer

from domains.models import Domain


logger = logging.getLogger(__name__)


class DomainSerializer(ModelSerializer):
    class Meta:
        model = Domain
        fields = (
            'id', 'name', 'description', 'domain', 'id_provider',
        )
