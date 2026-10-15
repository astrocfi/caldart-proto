"""Health and backup endpoints -- ``system_admin`` only.

These are the endpoints behind the portal's Health and database page
(``/portal/system/health``): is the box healthy, take a dump, download one.
Everything destructive (restore, reset) stays on the command line deliberately; it
is not something to do from a browser tab.
"""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet
from django.http import FileResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsSystemAdmin
from apps.aircraft import registry
from apps.aircraft.api.serializers import RegistryImportSerializer
from apps.payments.api.serializers import (
    RenewalRunRequestSerializer,
    RenewalRunResultSerializer,
    RenewalScanSerializer,
    StatementsRunRequestSerializer,
    StatementsRunResultSerializer,
)
from apps.payments.models import RenewalScan
from apps.payments.renewals.background import (
    ScanAlreadyRunningError,
    close_if_stale,
    start_scan,
)
from apps.payments.renewals.scan import run_auto_renewals
from apps.payments.statements import send_year_statements
from apps.sysadmin import services
from apps.sysadmin.api.serializers import (
    BackupSerializer,
    HealthSerializer,
    JobRunDetailSerializer,
    JobRunSerializer,
    JobStatusSerializer,
)
from apps.sysadmin.jobs import JOBS_BY_KEY, job_statuses
from apps.sysadmin.models import JobRun
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
        ``version`` is the project version; ``debug`` reports whether the
        server runs with ``DEBUG`` on; and ``scheduled_jobs`` is what
        ``GET /system/jobs`` answers, or empty when ``db`` is not ``"ok"``.
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

    @extend_schema(
        request=RenewalRunRequestSerializer,
        responses={
            200: RenewalRunResultSerializer,
            202: RenewalScanSerializer,
            409: OpenApiResponse(description="A live run is already under way."),
        },
    )
    def post(self, request: Request) -> Response:
        """Rehearse the scan and answer its counts, or start a live scan and answer 202.

        The body takes ``dry_run``, defaulting to ``False``.  A dry run changes no
        mandate, emails nobody and charges nobody, and runs inside the request: the
        answer is 200 with ``{noticed, warned, charged, failed, paused, skipped,
        actions}``, where ``actions`` names every member the run would email or
        charge, and the rehearsal is recorded in the audit log with the caller as
        its actor.

        A live scan charges cards, and each charge waits on the provider, so it is
        started in its own process (:func:`~apps.payments.renewals.background.start_scan`)
        and the answer is 202 with its ``RenewalScan`` row, unfinished: ``{id,
        started_at, finished_at: null, ok: false, error: "", result: null}``.  The
        scan fills the row in when it ends, and its ``renewals.run`` audit record
        names the caller.  ``GET /system/renewals/runs/{id}`` reads it back.  While
        another live scan started here is unfinished and younger than
        ``RENEWAL_STALE_MINUTES`` the answer is 409 with ``An automatic renewal run is
        already under way.``, and a WARNING ``renewals.run`` audit record with the
        reason ``run_in_progress`` is written instead.
        """
        payload = RenewalRunRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        if not payload.validated_data["dry_run"]:
            actor = _actor(request)
            try:
                scan = start_scan(actor)
            except ScanAlreadyRunningError as exc:
                audit.refuse(audit.RENEWALS_RUN, actor=actor, reason=audit.REASON_RUN_IN_PROGRESS)
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
            return Response(RenewalScanSerializer(scan).data, status=status.HTTP_202_ACCEPTED)
        run = run_auto_renewals(dry_run=True, actor=_actor(request))
        return Response(RenewalRunResultSerializer(run.as_dict()).data)


class RenewalScanView(APIView):
    """``GET /system/renewals/runs/{id}`` -- how a live scan from the portal went."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(responses={200: RenewalScanSerializer})
    def get(self, request: Request, pk: int) -> Response:
        """Return the ``RenewalScan`` row ``pk`` with status 200.

        ``finished_at`` stays null while the scan runs.  A scan still unfinished
        ``RENEWAL_STALE_MINUTES`` after it started has lost its process, and is
        closed here as failed with the error ``Did not finish.``.  Raises a 404
        :class:`~rest_framework.exceptions.NotFound` when there is no such row.
        """
        scan = RenewalScan.objects.filter(pk=pk).first()
        if scan is None:
            raise NotFound("No such renewal run.")
        return Response(RenewalScanSerializer(close_if_stale(scan)).data)


class StatementsRunView(APIView):
    """``POST /system/statements/run`` -- run the year-end statement sender now."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(
        request=StatementsRunRequestSerializer, responses={200: StatementsRunResultSerializer}
    )
    def post(self, request: Request) -> Response:
        """Run the sender and return its counts with status 200.

        The body takes ``dry_run``, defaulting to ``False``, and ``year``,
        defaulting to the calendar year before today.  A dry run writes and
        emails nothing and reports the accounts a live run would reach.  The
        answer is ``{year, sent, skipped, failed, actions}``, where ``actions``
        names every account the run emailed -- or, in a rehearsal, would have --
        and the caller is recorded as the actor on the ``statements.run`` audit
        record.
        """
        payload = StatementsRunRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        year = data["year"] if data["year"] is not None else timezone.localdate().year - 1
        run = send_year_statements(year, dry_run=data["dry_run"], actor=_actor(request))
        return Response(StatementsRunResultSerializer(run.as_dict()).data)


class RegistryImportRunView(APIView):
    """``POST /admin/system/registry-import`` -- start the FAA registry import now."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(
        request=None,
        responses={
            202: RegistryImportSerializer,
            409: OpenApiResponse(description="An import is already running."),
        },
    )
    def post(self, request: Request) -> Response:
        """Start ``import_faa_registry`` in its own process and answer 202 with its row.

        The row (started, not finished, its source ``FAA_REGISTRY_URL``, started by the
        caller) is written before the answer, and a ``system.registry_import`` audit
        record names the caller and the row.  While another import runs the answer is
        409 with ``An import is already running.``, and a WARNING audit record with
        reason ``import_running`` is written instead; an unfinished import older than
        ``REGISTRY_IMPORT_STALE_MINUTES`` is closed as failed and does not block.
        """
        actor = _actor(request)
        try:
            run = registry.start_import(actor)
        except registry.ImportAlreadyRunningError as exc:
            audit.refuse(audit.REGISTRY_IMPORT, actor=actor, reason=audit.REASON_IMPORT_RUNNING)
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        audit.record(audit.REGISTRY_IMPORT, actor=actor, target=run)
        return Response(RegistryImportSerializer(run).data, status=status.HTTP_202_ACCEPTED)


class JobListView(APIView):
    """``GET /system/jobs`` -- every scheduled job and how it stands."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(responses={200: JobStatusSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with one ``{job, name, state, last_run, missed_at}`` per job, unpaginated.

        The jobs come in the order the server runs them through a day, and each is
        judged as :func:`~apps.sysadmin.jobs.job_statuses` describes.
        """
        return Response(JobStatusSerializer(job_statuses(), many=True).data)


class JobRunListView(ListAPIView[JobRun]):
    """``GET /system/jobs/{job}/runs`` -- one job's recorded runs, newest first.

    Paginated; each row is a run without its output.  Answers 404 with
    ``No such scheduled job.``
    for a ``job`` that is not a key of the table of jobs.
    """

    permission_classes = [IsSystemAdmin]
    serializer_class = JobRunSerializer

    def get_queryset(self) -> QuerySet[JobRun]:
        """The runs of the job the URL names, newest first, with who started them."""
        job = self.kwargs["job"]
        if job not in JOBS_BY_KEY:
            raise NotFound("No such scheduled job.")
        return JobRun.objects.filter(job=job).select_related("started_by")

    def get_serializer_context(self) -> dict[str, Any]:
        """The standard context plus ``now``, so every row is judged at one moment."""
        return {**super().get_serializer_context(), "now": timezone.now()}


class JobRunDetailView(RetrieveAPIView[JobRun]):
    """``GET /system/jobs/runs/{id}`` -- one recorded run with its whole output.

    Answers 404 for an id no run has, including one pruned for its age.
    """

    permission_classes = [IsSystemAdmin]
    serializer_class = JobRunDetailSerializer
    queryset = JobRun.objects.select_related("started_by")
