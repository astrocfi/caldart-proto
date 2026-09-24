"""Health and backup endpoints -- ``system_admin`` only.

These are the screens behind ``/portal/system``: is the box healthy, take a
dump, download one.  Everything destructive (restore, reset) stays on the
command line deliberately; it is not something to do from a browser tab.
"""

from __future__ import annotations

from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsSystemAdmin
from apps.payments.api.serializers import (
    RenewalRunRequestSerializer,
    RenewalRunResultSerializer,
)
from apps.payments.renewals import run_auto_renewals
from apps.sysadmin import services
from apps.sysadmin.api.serializers import BackupSerializer, HealthSerializer
from caldart import audit
from caldart.reports import download_responses

#: The media type a database dump is served with.
BACKUP_MEDIA_TYPE = "application/gzip"


def _actor(request: Request) -> User:
    """The signed-in user making ``request``, for an audit record's ``actor``.

    ``IsSystemAdmin`` runs before any handler in this module and rejects an
    anonymous caller, so the request is authenticated by the time this runs;
    that permission class is the whole of the guarantee.  An assertion restates
    it for the type checker, so a request that somehow reaches here unauthenticated
    raises ``AssertionError`` and the caller sees a 500 rather than an audit
    record naming the wrong actor.  Python run with ``-O`` skips the assertion,
    leaving only the permission class.
    """
    assert isinstance(request.user, User)  # noqa: S101 - mypy strict narrowing, not test code
    return request.user


class HealthView(APIView):
    """``GET /system/health`` -- database, migrations, disk, last backup."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(responses={200: HealthSerializer})
    def get(self, request: Request) -> Response:
        """Return the health payload with status 200.

        The body is a single object: ``db`` is ``"ok"`` when a trivial query
        succeeds and ``"error: <message>"`` when it does not; ``pending_migrations``
        counts the migrations on disk that are not applied, and is ``-1`` when
        ``db`` is not ``"ok"``; ``disk_free_mb`` is the free space on the backup
        directory's filesystem in whole mebibytes; ``last_backup`` is the
        modification time of the newest dump, or ``null`` when there is none;
        ``version`` is the project version; and ``debug`` reports whether the
        server runs with ``DEBUG`` on.
        """
        return Response(HealthSerializer(services.health()).data)


class BackupListCreateView(APIView):
    """``GET /system/backups`` and ``POST /system/backups``."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(responses={200: BackupSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """List existing dumps, newest first, as ``{name, size_bytes, created_at}``."""
        backups = [backup.as_dict() for backup in services.list_backups()]
        # rest_framework-stubs' BaseSerializer.__init__ types `instance` as `_IN | None`
        # and does not model the `many=True` overload, which actually takes a sequence.
        return Response(BackupSerializer(backups, many=True).data)  # type: ignore[arg-type]

    @extend_schema(request=None, responses={201: BackupSerializer})
    def post(self, request: Request) -> Response:
        """Create a new dump and return it with status 201.

        The body is the created dump as ``{name, size_bytes, created_at}``, and a
        ``backup.create`` audit record naming the caller, the file and its size is
        written before the response.

        Raises a 400 :class:`~rest_framework.exceptions.ValidationError` when
        ``pg_dump`` and docker are both unavailable, or ``pg_dump`` itself fails;
        nothing is recorded in that case.
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
    """``GET /system/backups/{name}/download`` -- streams the gzipped dump.

    ``name`` is checked by :func:`apps.sysadmin.services.resolve_backup`, which
    only accepts a plain ``*.sql.gz`` file name resolving inside ``BACKUP_DIR``.
    """

    permission_classes = [IsSystemAdmin]

    @extend_schema(responses=download_responses(BACKUP_MEDIA_TYPE, "The gzipped database dump."))
    def get(self, request: Request, name: str) -> FileResponse:
        """Stream the gzipped dump called ``name`` as an attachment.

        The response carries the file with content type ``application/gzip`` and
        the dump's own name, and a ``backup.download`` audit record naming the
        caller and the file is written first.

        Raises a 404 :class:`~rest_framework.exceptions.NotFound` in two cases:
        ``name`` is not a plain ``*.sql.gz`` file name resolving inside
        ``BACKUP_DIR``, with the detail ``Not a backup file name: '<name>'``; or
        it is such a name but no file of that name exists, with the detail
        ``No such backup: <name>``.  Either refusal writes a WARNING
        ``backup.download`` audit record with reason ``no_such_backup`` instead
        of the success record; the refused name itself is not recorded.
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
            content_type=BACKUP_MEDIA_TYPE,
        )


class RenewalRunView(APIView):
    """``POST /system/renewals/run`` -- run the automatic-renewal scan now."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(request=RenewalRunRequestSerializer, responses={200: RenewalRunResultSerializer})
    def post(self, request: Request) -> Response:
        """Run the scan and return its counts with status 200.

        The body takes ``dry_run``, defaulting to ``False``; a dry run changes no
        mandate, emails nobody and charges nobody, and reports the counts the
        same scan would produce.  The rehearsal is recorded in the audit log like
        any other run.  The answer is ``{noticed, warned, charged,
        failed, paused, skipped}``, and the caller is recorded as the actor on the
        ``renewals.run`` audit record.
        """
        payload = RenewalRunRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        run = run_auto_renewals(dry_run=payload.validated_data["dry_run"], actor=_actor(request))
        return Response(RenewalRunResultSerializer(run.as_dict()).data)
