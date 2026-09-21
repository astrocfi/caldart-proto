"""Abstract model bases every app builds on."""

from django.db import models


class TimestampedModel(models.Model):
    """Every model in the project carries ``created_at``/``updated_at``."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
