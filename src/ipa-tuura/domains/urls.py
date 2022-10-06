#
# Copyright (C) 2023  FreeIPA Contributors see COPYING for license
#

"""Integration Domain URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import logging

from django.urls import include, re_path
from rest_framework.routers import DefaultRouter
from domains.views import DomainViewSet

logger = logging.getLogger(__name__)


router = DefaultRouter()
router.register('domain', DomainViewSet)

urlpatterns = [
    re_path('^', include(router.urls)),
]
