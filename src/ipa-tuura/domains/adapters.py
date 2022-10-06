#
# Copyright (C) 2023  FreeIPA Contributors see COPYING for license
#

import logging

from rest_framework.serializers import ModelSerializer

from domains.models import Domain


logger = logging.getLogger(__name__)


class DomainSerializer(ModelSerializer):
    class Meta:
        model = Domain
        fields = (
            'id',
            'name',
            'description',
            'integration_domain_url',
            'client_id',
            'client_secret',
            'id_provider',
            'user_extra_attrs',
            'user_object_classes',
            'users_dn',
            'ldap_tls_cacert',
        )
