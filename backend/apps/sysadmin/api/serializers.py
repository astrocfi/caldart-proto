"""Serializers for the system endpoints."""

from __future__ import annotations

from rest_framework import serializers


class HealthSerializer(serializers.Serializer):
    """``GET /system/health``."""

    db = serializers.CharField()
    pending_migrations = serializers.IntegerField()
    disk_free_mb = serializers.IntegerField()
    last_backup = serializers.DateTimeField(allow_null=True)
    version = serializers.CharField()
    debug = serializers.BooleanField()


class BackupSerializer(serializers.Serializer):
    """One entry of ``GET /system/backups``."""

    name = serializers.CharField()
    size_bytes = serializers.IntegerField()
    created_at = serializers.DateTimeField()
