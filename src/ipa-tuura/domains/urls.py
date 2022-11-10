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
