#
# Copyright (C) 2023  FreeIPA Contributors see COPYING for license
#

import logging

from django.http import Http404
from domains.adapters import DomainSerializer
from domains.models import Domain
from domains.utils import add_domain, delete_domain
from rest_framework import status
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
)
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

logger = logging.getLogger(__name__)


class DomainViewSet(
    GenericViewSet,
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    DestroyModelMixin,
):
    serializer_class = DomainSerializer
    queryset = Domain.objects.all()

    # handles CreateModelMixin POSTs
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            add_domain(serializer.validated_data)
        except RuntimeError as e:
            return Response(str(e), status=status.HTTP_405_METHOD_NOT_ALLOWED)
        except Exception as e:
            raise e
        else:
            self.perform_create(serializer)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # handles GETs for 1 Domain
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        logger.info(f"domain retrieve {serializer.data}")

        return Response(serializer.data)

    # handles GETs for many Domains
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data)

    # handles DELETEs for 1 Domain
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            logger.info(f"domain destroy {serializer.data}")
            delete_domain(serializer.data)
            self.perform_destroy(instance)
        except Http404:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)
