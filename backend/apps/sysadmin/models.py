"""The record of every scheduled job's runs."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class JobRun(models.Model):
    """One run of a scheduled job through ``manage.py run_job``, whatever its outcome.

    ``job`` is the key of the job in :data:`apps.sysadmin.jobs.JOBS`, and ``arguments``
    the options the command was given after its name.  ``finished_at`` and
    ``exit_status`` are null while the run is under way.  ``started_by`` is the system
    administrator who started it with **Run now**, null for a run the server started.
    ``output`` holds what the command wrote to its standard output and standard error,
    interleaved in the order it wrote them, cut to its last
    :data:`~apps.sysadmin.recording.OUTPUT_LIMIT` characters with ``output_truncated``
    set when it ran longer.  ``error`` is a failed run's message, and ``traceback``
    the traceback of an unexpected exception.  ``idle`` marks a run that succeeded
    without finding anything to do; a job keeps only its newest idle run.
    """

    class Outcome(models.TextChoices):
        """How a run ended, or that it has not yet."""

        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    job = models.CharField(max_length=32)
    arguments = models.CharField(max_length=500, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=12, choices=Outcome.choices, default=Outcome.RUNNING)
    exit_status = models.SmallIntegerField(null=True, blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="job_runs",
    )
    output = models.TextField(blank=True)
    output_truncated = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    traceback = models.TextField(blank=True)
    idle = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at", "-id"]
        indexes = [
            models.Index(fields=["job", "-started_at"], name="sysadmin_jobrun_job_started"),
            models.Index(fields=["started_at"], name="sysadmin_jobrun_started"),
        ]

    def __str__(self) -> str:
        """Return the job, when the run started, and its outcome."""
        return f"{self.job} {self.started_at:%Y-%m-%d %H:%M} ({self.outcome})"
