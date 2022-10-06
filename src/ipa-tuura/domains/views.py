import logging

from rest_framework.mixins import (
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin
)
from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework import status

from domains.models import Domain
from domains.adapters import DomainSerializer
from domains.utils import (
    list_domains,
)


logger = logging.getLogger(__name__)


class DomainViewSet(GenericViewSet,
                    CreateModelMixin,
                    RetrieveModelMixin,
                    UpdateModelMixin,
                    DestroyModelMixin,
                    ListModelMixin):
    serializer_class = DomainSerializer
    queryset = Domain.objects.all()

    # save domain back to the database
    def perform_save(self, serializer):
        serializer.save()

    # handles CreateModelMixin POSTs
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        self.perform_save(serializer)

        logger.info(f'domain create {serializer.data}')

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # handles GETs for 1 Domain
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        logger.info(f'domain retrieve {serializer.data}')

        return Response(serializer.data)

    # handles PATCHes
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True

        return self.update(request, *args, **kwargs)

    # handles PUTs
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial
            )

        serializer.is_valid(raise_exception=True)

        logger.info(f'domain update {serializer.data}')

        self.perform_save(serializer)

        return Response(serializer.data)

    # handles GETs for many Domains
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)

        sssddomains = list_domains()

        logger.info(f'domain retrieve active domains list {sssddomains}')

        return Response(serializer.data)

    # handles DELETEs for 1 Domain
    def destroy(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial
            )

        serializer.is_valid(raise_exception=True)

        logger.info(f'domain destroy {serializer.data}')

        self.perform_save(serializer)

        return Response(serializer.data)
