"""``manage.py check_mail_dns`` -- check the DNS records that make mail deliverable.

Looks up the SPF, DKIM, and DMARC records for the domain of ``DEFAULT_FROM_EMAIL`` and
prints one line per finding with its fix.  Always queries the name servers afresh.  Run
it by hand after changing DNS or the mail server; the Mail delivery screen shows the
same report.  A warning leaves the exit status at zero; any failing finding makes the
command exit non-zero.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.mail.dns_check import DnsReport, DnsStatus, check_mail_dns


class Command(BaseCommand):
    """Prints the mail delivery report to stdout."""

    help = "Check the SPF, DKIM, and DMARC records for the site's From address."

    def handle(self, *args: Any, **options: Any) -> None:
        """Run the check and print every finding.

        Raises ``CommandError`` (exit status 1) when any finding is a ``fail``, after
        the whole report has been printed.
        """
        report = check_mail_dns(now=timezone.now(), refresh=True)
        self._print(report)
        failures = [f for f in report.findings if f.status == DnsStatus.FAIL]
        if len(failures) > 0:
            raise CommandError(f"{len(failures)} mail delivery check(s) failed.")

    def _print(self, report: DnsReport) -> None:
        """Write the report's heading and one block per finding to stdout."""
        domain = report.domain if report.domain != "" else "(no domain)"
        self.stdout.write(f"Mail delivery for {domain}")
        styles = {
            DnsStatus.PASS: self.style.SUCCESS,
            DnsStatus.WARN: self.style.WARNING,
            DnsStatus.FAIL: self.style.ERROR,
        }
        for finding in report.findings:
            self.stdout.write(
                styles[finding.status](f"[{finding.status.value.upper()}] {finding.name}")
            )
            self.stdout.write(f"  {finding.detail}")
            if finding.fix != "":
                self.stdout.write(f"  Fix: {finding.fix}")
