#
# Copyright (C) 2024  FreeIPA Contributors see COPYING for license
#

import logging
import threading

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
from scim.ipa import IPA

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
        logger.info(f"domain create {serializer.validated_data}")

        # Define the background process for handling the domain addition
        def process_domain_creation():
            try:
                add_domain(serializer.validated_data)
            except Exception as e:
                logger.error(f"Unexpected error during domain creation: {str(e)}")
                raise e
            else:
                self.perform_create(serializer)

            # reset the writable interface
            ipa = IPA()
            ipa._reset_instance()

        # Run the domain creation logic in a separate thread
        thread = threading.Thread(target=process_domain_creation)
        thread.start()

        # Return the created response
        return Response(serializer.validated_data, status=status.HTTP_202_ACCEPTED)

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

        # Define the background process for handling the domain destroy
        def process_domain_destroy():
            try:
                instance = self.get_object()
                serializer = self.get_serializer(instance)
                logger.info(f"domain destroy {serializer.data}")
                delete_domain(serializer.data)
                self.perform_destroy(instance)
            except Exception as e:
                logger.error(f"Unexpected error during domain destroy: {str(e)}")
                raise e

        # Run the domain destroy logic in a separate thread
        thread = threading.Thread(target=process_domain_destroy)
        thread.start()

        return Response(status=status.HTTP_202_ACCEPTED)
