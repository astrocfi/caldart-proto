"""Serializers for the system endpoints."""

from __future__ import annotations

from typing import Any

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.sysadmin.jobs import JOB_STATES, JOBS_BY_KEY, RUN_OUTCOMES, run_outcome
from apps.sysadmin.models import JobRun


class BackupSerializer(serializers.Serializer[dict[str, Any]]):
    """One entry of ``GET /system/backups``."""

    name = serializers.CharField()
    size_bytes = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class JobRunSerializer(serializers.ModelSerializer[JobRun]):
    """One recorded run of a scheduled job, without its output.

    ``name`` is the job's name on the System pages.  ``outcome`` is ``running``,
    ``succeeded``, ``failed``, or ``stopped`` for a run still unfinished past its job's
    stale limit.  ``started_by_name`` is the system administrator who started it with
    **Run now**, blank for a run the server started.  ``finished_at`` and
    ``exit_status`` are null while it runs.
    """

    name = serializers.SerializerMethodField()
    outcome = serializers.SerializerMethodField()
    started_by_name = serializers.SerializerMethodField()

    class Meta:
        model = JobRun
        fields = [
            "id",
            "job",
            "name",
            "arguments",
            "started_at",
            "finished_at",
            "outcome",
            "exit_status",
            "started_by_name",
            "error",
        ]
        read_only_fields = fields

    def get_name(self, run: JobRun) -> str:
        """The job's name, or its key for a job no longer in the table."""
        job = JOBS_BY_KEY.get(run.job)
        return run.job if job is None else job.label

    @extend_schema_field(serializers.ChoiceField(choices=RUN_OUTCOMES))
    def get_outcome(self, run: JobRun) -> str:
        """The run's outcome as of the request: see the class docstring."""
        return run_outcome(run, self.context.get("now") or timezone.now())

    def get_started_by_name(self, run: JobRun) -> str:
        """Who pressed **Run now**, or blank for the server."""
        return "" if run.started_by is None else run.started_by.display_name


class JobRunDetailSerializer(JobRunSerializer):
    """One recorded run with everything it wrote.

    ``output`` is standard output and standard error interleaved, its last 65,536
    characters when ``output_truncated``; ``traceback`` is blank unless an unexpected
    exception stopped the run.
    """

    class Meta(JobRunSerializer.Meta):
        fields = [*JobRunSerializer.Meta.fields, "output", "output_truncated", "traceback"]
        read_only_fields = fields


class JobStatusSerializer(serializers.Serializer[Any]):
    """One scheduled job, judged from its latest run and its schedule.

    ``state`` is one of ``ok``, ``running``, ``waiting`` (nothing due yet), ``failed``,
    ``stopped``, ``overdue``, and ``never_run``; ``missed_at`` is the trigger no run
    followed, for ``overdue`` and ``never_run``, and null otherwise.  ``last_run`` is the
    job's latest run, whoever started it, or null.
    """

    job = serializers.CharField(source="job.key")
    name = serializers.CharField(source="job.label")
    state = serializers.ChoiceField(choices=JOB_STATES)
    last_run = JobRunSerializer(allow_null=True)
    missed_at = serializers.DateTimeField(allow_null=True)


class HealthSerializer(serializers.Serializer[dict[str, Any]]):
    """``GET /system/health``."""

    db = serializers.CharField()
    pending_migrations = serializers.IntegerField()
    disk_free_mb = serializers.IntegerField()
    last_backup = serializers.DateTimeField(allow_null=True)
    version = serializers.CharField()
    debug = serializers.BooleanField()
    scheduled_jobs = JobStatusSerializer(many=True, allow_null=True)
