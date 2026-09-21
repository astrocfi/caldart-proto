"""Health and backup endpoints — ``system_admin`` only.

These are the screens behind ``/portal/system``: is the box healthy, take a
dump, download one.  Everything destructive (restore, reset) stays on the
command line deliberately; it is not something to do from a browser tab.
"""

from __future__ import annotations

from django.http import FileResponse
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSystemAdmin
from apps.sysadmin import services
from apps.sysadmin.api.serializers import BackupSerializer, HealthSerializer
from caldart import audit


class HealthView(APIView):
    """``GET /system/health`` — database, migrations, disk, last backup."""

    permission_classes = [IsSystemAdmin]

    def get(self, request):
        return Response(HealthSerializer(services.health()).data)


class BackupListCreateView(APIView):
    """``GET /system/backups`` and ``POST /system/backups``."""

    permission_classes = [IsSystemAdmin]

    def get(self, request):
        backups = [backup.as_dict() for backup in services.list_backups()]
        return Response(BackupSerializer(backups, many=True).data)

    def post(self, request):
        try:
            backup = services.create_backup()
        except services.BackupError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        audit.record(
            audit.BACKUP_CREATE,
            actor=request.user,
            file=backup.name,
            size=backup.size_bytes,
        )
        return Response(
            BackupSerializer(backup.as_dict()).data,
            status=status.HTTP_201_CREATED,
        )


class BackupDownloadView(APIView):
    """``GET /system/backups/{name}/download`` — streams the gzipped dump.

    ``name`` is checked by :func:`apps.sysadmin.services.resolve_backup`, which
    only accepts a plain ``*.sql.gz`` file name resolving inside ``BACKUP_DIR``.
    """

    permission_classes = [IsSystemAdmin]

    def get(self, request, name: str):
        try:
            path = services.resolve_backup(name)
        except services.BackupError as exc:
            # The refused name came off the URL, so only the refusal is recorded.
            audit.refuse(
                audit.BACKUP_DOWNLOAD, actor=request.user, reason=audit.REASON_NO_SUCH_BACKUP
            )
            raise NotFound(str(exc)) from exc

        audit.record(audit.BACKUP_DOWNLOAD, actor=request.user, file=path.name)
        return FileResponse(
            path.open("rb"),
            as_attachment=True,
            filename=path.name,
            content_type="application/gzip",
        )
