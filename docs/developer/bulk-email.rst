==========
Bulk email
==========

CalDART management writes one email to many members and friends at once: a
newsletter, a seminar notice, a call for volunteers.  The email is a draft on the
server from the moment Compose opens it, its people are a *batch* built from the
member list's own filters, and **Send** only queues it.  A background sender,
started every minute by a systemd timer like the other scheduled jobs, sends the
copies, paced to the mail provider's limit, and records what became of each.

The code is in ``apps/bulk_email/``, the templates are ``bulk_email`` and
``bulk_email_copy`` in ``backend/templates/emails/``, and the endpoints are in
:doc:`api-bulk-email`.  The models are in :ref:`data-model-bulk-email`.


The modules
===========

``apps/bulk_email/`` keeps each concern in a module of its own, so that a feature
added later lands in a file of its own rather than growing one:

``models.py``
    ``BulkEmail``, ``BatchAdd``, ``BulkEmailRecipient``, and their choices.
``batch.py``
    The batch: adding by filters, the skip reasons, the batch as rows and as a
    CSV, and a send's results as a CSV.  ``locked_for_edit`` is the edit rule.
``drafts.py``
    A draft's life before the sender takes it: open or reuse a draft, change it,
    queue it (**Send**), cancel it, stop it, and send the rest.
``job.py``
    The background sender: claim, freeze, the paced send loop, the retries, and
    the progress estimate.
``render.py``
    ``render_copy``: one recipient's copy, its subject, its two bodies, and its
    headers.
``api/``
    The endpoints: ``drafts.py``, ``batch.py``, ``history.py``, and
    ``sender.py`` (**Run now**), with the serializers in ``serializers.py``.
``management/commands/send_bulk_emails.py``
    One run of the sender.


States
======

.. code-block:: text

   draft --Send--> queued --(start_at arrives, the sender claims it)--> sending --> sent
     ^               |                                                      |
     +----Cancel-----+                                                      +--Stop--> stopped
                                                                                         |
                       queued <-------------------Send the rest--------------------------+

``draft``
    Being written.  ``POST /bulk-email/drafts`` hands a sender their one empty
    draft (no subject, no message, nobody in the batch) or a fresh one, so pressing
    Compose twice does not leave two empty drafts behind.
``queued``
    **Send** checks the email can go and sets ``start_at``: now plus
    ``BULK_EMAIL_UNDO_SECONDS``, the undo window, or the time the sender chose
    (``scheduled``).  Above ``BULK_EMAIL_CONFIRM_ABOVE`` recipients the sender must
    type the count, and the server counts the batch again, so a batch that grew
    after the count was typed is refused with its new size.  A queued email can
    still be changed, its content and its batch, and keeps its ``start_at``;
    sending it again reschedules it.  **Cancel** takes it back to a draft.
``sending``
    The sender has claimed it and frozen its batch.  Nothing about it can change
    any more, except that **Stop** asks the sender to stop.
``sent``
    Every copy has been tried.  One ``bulk_email.send`` audit line names the
    sender and the counts.
``stopped``
    **Stop** reached the sender between copies.  Every copy not yet sent is
    ``stopped``, with *Stopped by* and the name of whoever pressed it.  **Send the
    rest** turns those rows back to ``pending`` and queues the email to start at
    once, with no undo window.

The edit rule is one function, ``batch.locked_for_edit``: it reads the email under
its row lock (``select_for_update``) and refuses with *This email has been sent and
cannot be changed.* unless the email is a ``draft`` or ``queued``.  Every change to
the content or the batch, and **Send** itself, goes through it inside a
transaction, so a change and the sender's claim of the same email never overlap.


The batch
=========

Each **Add to batch** runs the member list's filters
(``apps.members.filters.MemberAdminFilterSet``, with deactivated accounts
included) and inserts a ``batched`` row for every account not already in the
batch, by account, with the account's name, address, kind, and DART as they are
then, and a ``BatchAdd`` recording the filters and the two counts.  The batch is
the union of every add, so "everyone in the Marin DART, plus every pilot with a
lapsed medical, plus all friends" is three adds and nobody hears twice.

Whether a person receives a copy is never stored while the email is a draft.
``batch.batch_rows`` works it out whenever the batch is read, from each account as
it is then, walking the batch in surname order: ``skip_reason(account, seen)``
asks, in order, whether the account is deleted, deactivated, without an address,
with an address no mail server would take, or with an address that bounced, and
then whether ``seen`` already holds the address, trimmed and case-folded.  So an
address that bounced after somebody was added shows as skipped at once, and two
accounts sharing one address get one copy, the first in surname order.


The sender
==========

``job.run_sender`` is one run of the sender.  ``manage.py send_bulk_emails`` calls
it every minute, from ``caldart-bulk-email.timer`` (:ref:`deploy-bulk-email`),
and ``POST /system/bulk-email/run`` calls it from the Scheduled page's **Run now**.

Only one run works at a time.  A run takes a PostgreSQL advisory lock for as long
as it works, and a run that cannot take it returns at once with ``busy`` set; the
lock belongs to the database session, so it is released however the run ends.
systemd does not start a second instance of a running oneshot either, but the
lock is what keeps **Run now** and the timer from sending the same copies.

A run first finishes every email left ``sending``, which only a run that died part
way leaves behind: its ``pending`` rows are simply sent, and the rows already
tried are left alone.  Then it claims each ``queued`` email whose ``start_at`` has
come, one at a time, in a short transaction that takes the row with
``select_for_update(skip_locked=True)``, sets it ``sending`` and ``started_at``,
and **freezes the batch**: each ``batched`` row takes its account's name, address,
kind, and DART as they are at that moment, and becomes ``pending``, or ``skipped``
with the reason ``batch_rows`` gives it then, which ``skipped_count`` counts.  An
email whose row another transaction holds, such as one whose batch is being
changed that instant, is left for the next run.

The pending rows are then sent in surname order, one copy each.  Each row and the
email's counts are saved as soon as its copy has been tried, outside any
transaction, so the record is exact however the run ends.  Between copies the run
reads ``stop_requested`` afresh.  When no row is pending, the email is ``sent``
and ``sent_at`` set.

.. _bulk-email-pacing:

Pacing and refusals
-------------------

The sender sends at most ``BULK_EMAIL_RATE_PER_MINUTE`` copies a minute: after a
copy begins it sleeps out whatever is left of 60 / rate seconds before the next,
so the rate is a ceiling however fast the mail server answers.  It opens one mail
connection, and a fresh one every ``BULK_EMAIL_BATCH_SIZE`` copies and after any
refused copy, rather than writing to a session the server may have dropped.

A copy goes through ``caldart.mail.send_templated``, so it is in the email log
under the purpose ``bulk_email`` like any other message, and its ``Message-ID`` is
stored on the row as well as on the log row.  A refusal is a
``caldart.mail.MailRefusedError`` carrying the SMTP reply code:

* A **temporary** refusal, reply code 421, 450, 451, or 452, is tried again after
  5, 15, and 45 seconds, over a fresh connection each time.  After the third
  retry the copy is ``failed`` with *Temporarily refused, gave up after 3
  retries*.
* Any **other** refusal, a 5xx reply or a transport error with no code, fails the
  copy at once with *Refused by the mail server*.

Either way the rest still go.  A refusal is logged on the ``apps.bulk_email.job``
logger with the email's and the row's ids, never the address.

Progress
--------

``GET /bulk-email/{id}`` carries ``sent_count``, ``failed_count``,
``skipped_count``, ``remaining`` (the ``pending`` rows), and, while the email is
sending, ``estimated_finish_at``: now plus ``remaining`` copies at the rate.  The
compose screen and the Sent page read it every three seconds while the email is
``queued`` or ``sending``.


Rendering a copy
================

``render.render_copy(bulk, recipient)`` returns a ``RenderedCopy``: the subject,
the plain-text and HTML bodies, and a dictionary of extra headers.  The bodies are
rendered from ``emails/bulk_email.{txt,html}``: the plain-text body is the
message followed by the house footer, and the HTML one makes each paragraph of
the message a ``<p>`` inside the shared report frame.  The sender hands the
finished bodies to ``send_templated`` through the pass-through pair
``emails/bulk_email_copy.{txt,html}``, which print the ``text`` and ``html`` they
are given unchanged, and passes the copy's ``headers`` through
``send_templated``'s ``headers`` argument.  Every copy of one email reads the same
today, and carries no extra header.


Extending
=========

The pieces a feature added to bulk email changes, and where:

* A new **skip reason**, such as an opt-out from a type of email or a limit to one
  DART, goes in ``batch.skip_reason``, which both the batch screen and the freeze
  read, so the reason shows in the batch the moment it applies and is stored
  when the send starts.
* A new **field of the email**, such as its type or a ``Reply-To``, is a model
  field, a field of ``BulkEmailUpdateSerializer`` (``PATCH`` saves whatever that
  serializer validates through ``drafts.update``), and a check in ``drafts.queue``
  when **Send** must refuse without it.
* Anything that changes **what a copy says**, such as per-recipient fields, an
  unsubscribe link and its headers, or a Reply-To, goes in ``render_copy`` and in
  the arguments the sender passes to ``send_templated``.
* A new **screen** joins the Bulk Email group of the portal's menu
  (``frontend/src/portal/nav.ts``), its route goes in
  ``frontend/src/portal/routes/bulk-email.tsx``, and its guide page under
  ``docs/user/bulk-email/``.
