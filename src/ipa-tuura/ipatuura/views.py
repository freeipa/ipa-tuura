#
# Copyright (C) 2022  FreeIPA Contributors see COPYING for license
#

from django_scim.views import (
    GetView,
    PostView,
    PutView,
    PatchView,
    DeleteView,
    SCIMView
)

from ipatuura.adapters import DomainAdapter
from ipatuura.models import Domain


class DomainsView(GetView, PostView, PutView, PatchView, DeleteView, SCIMView):

    http_method_names = ['get', 'post', 'put', 'patch', 'delete']

    scim_adapter_getter = DomainAdapter
    model_cls_getter = Domain
