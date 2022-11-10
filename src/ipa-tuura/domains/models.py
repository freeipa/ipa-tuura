import logging

from django.db import models


logger = logging.getLogger(__name__)


class Domain(models.Model):
    name = models.CharField(max_length=80)
    description = models.TextField(blank=True)
    domain = models.URLField(blank=True)
    id_provider = models.CharField(max_length=10)

    def __str__(self):
        return self.name
