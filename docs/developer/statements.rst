==========
Statements
==========

Once a year, CalDART sends every account that gave a contribution a statement
of what it gave, for the giver's tax return.  As with the renewal scan
(:doc:`renewals`) and the report sender (:doc:`scheduled-reports`), there is no
queue and no worker: one management command, run yearly by a systemd timer,
sends whatever a calendar year owes, and a rerun for a year already sent
reaches nobody again.

The code is in ``apps/payments/statements.py``, the templates are
``contribution_statement`` in ``backend/templates/emails/``, and the endpoint
is in :doc:`api-system`.


Who is sent one
================

Every account that is **active**, whatever its :ref:`kind <account-kinds>` —
a member, a friend, or a donor — and that made at least one **settled**
contribution in the calendar year: a payment carrying a contribution whose
ledger date (:doc:`reports`) falls in that year, and whose status is
``succeeded``, ``partially_refunded`` or ``refunded``.  A deactivated account
is never written to, however much it gave while active; a pure membership
payment, carrying no contribution, earns no statement.

``givers_in_year(year)`` in ``apps/payments/statements.py`` finds them by the
same ledger-date rule ``Payment.paid_on`` applies: a payment recorded by hand
counts on its ``received_on`` date, and every other payment on the local date
its ``completed_at`` falls on.  A check received in December and keyed in
January counts in the year it arrived, the same year the member's own
statement and the payments, contributions, and donors reports put it in.


The statement
=============

Each giver's statement is the same PDF a member downloads from Payments at any
time (:doc:`/user/member/payments`): a line per settled contribution, netted against
whatever of it was refunded, and the year's total.  The email names the total,
carries the "no goods or services were provided in exchange for these
contributions" sentence a 501(c)(3) receipt requires, and, for a member or a
friend only, a link to Payments — a donor cannot sign in, so the email links
nowhere.  The subject is ``<org>: your <year> contribution statement``, and
the send is recorded in the email log under the purpose
``contribution_statement``.

A sent statement writes one ``YearStatement`` row (:ref:`data-model-year-statement`),
unique on the account and the year, so a rerun for a year already sent finds
the row and skips the account rather than sending the statement again.


The run
=======

``apps.payments.statements.send_year_statements`` is the single entry point:
the management command and ``POST /system/statements/run`` both call it.  It
takes the ``year`` to send statements for, and returns a ``StatementRun``:

``sent``
   the statements that went out, or in a dry run would have;
``skipped``
   accounts that already held a ``YearStatement`` for the year;
``failed``
   an address the mail server refused, logged at ERROR with the account's id,
   and an account with no address on file, logged at WARNING;
``actions``
   one line per statement: the account's name and address, and the year's net
   total as ``amount_cents``.

One giver's problem never stops the run.  Before sending, the account's
``YearStatement`` row for the year is claimed with ``get_or_create``, so two
runs started at once -- the timer and an operator's click on the System
screen, say -- cannot both email the same address: the second finds the row
already claimed and counts the account as skipped.  A dry run writes and
emails nothing, and reports exactly the statements a live run would send,
with the same totals, counting an account with no address on file as
``failed`` exactly as a live run would.  Every run ends with one
``statements.run`` audit line carrying the year, the mode, and the three
counts (:ref:`deploy-audit-log`).

The command
-----------

.. code-block:: console

   $ cd backend
   $ uv run python manage.py send_year_statements --dry-run --today 2026-01-15
   year             2025
   today            2026-01-15
   mode             dry run (nothing sent)
   sent             6
   skipped          0
   failed           0
   would email contribution_statement to Dana Doe <dana@example.org> $50.00
   ...
   would send 6, skipped 0

``--year`` names the calendar year to send statements for and defaults to the
year before ``--today`` (or before today, without it); ``--today`` runs as of
another date, which is how to rehearse the timer's own run; ``--dry-run``
sends nothing.  The command exits non-zero when any statement failed to send,
so the systemd unit goes to ``failed`` rather than reporting a clean run that
reached nobody.  In production ``caldart-statements.timer`` runs it yearly at
06:45 on January 15th (:ref:`deploy-statements`), well after every provider
has settled the prior December's payments.


Tests
=====

``backend/tests/test_year_statements.py`` covers who counts as a giver across
every kind of account and a deactivated one, the run's counts and actions, a
refund netted against the total, the dry run, a rerun sending nothing twice, a
refused send counted and retried once the mail server is back up, two claims
on one account within a single run, the audit line, the command, and the
endpoint's role matrix.  The email bodies are exercised through ``mailoutbox``
rather than a golden file, since the total they carry varies with the
fixtures each test builds.
