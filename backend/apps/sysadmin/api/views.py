"""Health and backup endpoints — ``system_admin`` only.

These are the screens behind ``/portal/system``: is the box healthy, take a
dump, download one.  Everything destructive (restore, reset) stays on the
command line deliberately; it is not something to do from a browser tab.
"""

from __future__ import annotations

from django.http import FileResponse
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsSystemAdmin
from apps.sysadmin import services
from apps.sysadmin.api.serializers import BackupSerializer, HealthSerializer
from caldart import audit


def _actor(request: Request) -> User:
    """The signed-in user making ``request``, for an audit record's ``actor``.

    Every view here requires ``IsSystemAdmin``, so the request is always
    authenticated by the time this runs.
    """
    assert isinstance(request.user, User)
    return request.user


class HealthView(APIView):
    """``GET /system/health`` — database, migrations, disk, last backup."""

    permission_classes = [IsSystemAdmin]

    def get(self, request: Request) -> Response:
        """Return the health payload from :func:`apps.sysadmin.services.health`."""
        return Response(HealthSerializer(services.health()).data)


class BackupListCreateView(APIView):
    """``GET /system/backups`` and ``POST /system/backups``."""

    permission_classes = [IsSystemAdmin]

    def get(self, request: Request) -> Response:
        """List existing dumps, newest first, as ``{name, size_bytes, created_at}``."""
        backups = [backup.as_dict() for backup in services.list_backups()]
        # rest_framework-stubs' BaseSerializer.__init__ types `instance` as `_IN | None`
        # and does not model the `many=True` overload, which actually takes a sequence.
        return Response(BackupSerializer(backups, many=True).data)  # type: ignore[arg-type]

    def post(self, request: Request) -> Response:
        """Create a new dump and return it with status 201.

        Raises a 400 :class:`~rest_framework.exceptions.ValidationError` when
        ``pg_dump`` and docker are both unavailable, or ``pg_dump`` itself fails.
        """
        try:
            backup = services.create_backup()
        except services.BackupError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        audit.record(
            audit.BACKUP_CREATE,
            actor=_actor(request),
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

    def get(self, request: Request, name: str) -> FileResponse:
        """Stream the gzipped dump called ``name``.

        Raises a 404 :class:`~rest_framework.exceptions.NotFound` when ``name``
        is not a plain ``*.sql.gz`` file name resolving inside ``BACKUP_DIR``.
        """
        try:
            path = services.resolve_backup(name)
        except services.BackupError as exc:
            # The refused name came off the URL, so only the refusal is recorded.
            audit.refuse(
                audit.BACKUP_DOWNLOAD, actor=_actor(request), reason=audit.REASON_NO_SUCH_BACKUP
            )
            raise NotFound(str(exc)) from exc

        audit.record(audit.BACKUP_DOWNLOAD, actor=_actor(request), file=path.name)
        return FileResponse(
            path.open("rb"),
            as_attachment=True,
            filename=path.name,
            content_type="application/gzip",
        )
