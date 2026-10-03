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
    ``BulkEmail``, ``BatchAdd``, ``BulkEmailRecipient``, ``BulkEmailImage``,
    ``EmailTemplate``, ``RecipientGroup`` with its ``RecipientGroupMember`` and
    ``RecipientGroupFilter`` rows, and their choices.
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
    ``render_copy`` and ``render_message``: one recipient's copy, its subject, its
    two bodies, and its headers; ``check_message``, what a token-bearing message
    is refused for; ``fill_values``, a person's values for the fields it uses.
``richtext.py``
    ``sanitize``, the allow-list a message's HTML is reduced to, and
    ``html_to_text``, the plain-text part derived from it.
``fields.py``
    The recipient fields a message can fill in, such as ``{first_name}``: the
    catalog, finding tokens, each person's values, and filling them in.
``images.py``
    The images put into a message: checked, scaled, and stored as
    ``BulkEmailImage`` rows under ``MEDIA_ROOT``.
``preview.py``
    One person's copy for the **Check and send** card's preview.
``templates.py``
    Reusing a message: filling a draft from a saved template, and **Duplicate**.
``groups.py``
    Saved recipient groups: who a group holds now, adding one to a batch, saving
    a batch as one, and changing a group's people or filters.
``api/``
    The endpoints: ``drafts.py``, ``batch.py``, ``history.py``, ``sender.py``
    (**Run now**), ``richtext.py`` (the field catalog and image uploads),
    ``preview.py``, ``templates.py`` (templates and **Duplicate**), and ``groups.py``
    (recipient groups), with the shared serializers in ``serializers.py``.
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
    after the count was typed is refused with its new size.  A queued email's
    content can still be changed, and it keeps its ``start_at``, but not left
    without a subject or a message; sending it again reschedules it.  Any change to
    its batch (an add, a removal, a clear) takes it back to a draft with its
    schedule cleared, since the count the sender confirmed no longer holds; one
    ``bulk_email.cancel`` audit line with the reason ``batch_changed`` says so.
    **Cancel** takes it back to a draft too.
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
    once, with no undo window.  **Stop** on that queued email stops it again at once,
    without waiting for the sender.

.. _bulk-email-edit-rule:

The edit rule is one function, ``batch.locked_for_edit``: it reads the email under
its row lock (``select_for_update``) and refuses with *This email has been sent and
cannot be changed.* unless ``BulkEmail.can_edit`` holds: the email is a ``draft``
or ``queued`` **and its** ``started_at`` **is not set**.  An email that has ever
started sending holds copies that went, so it never becomes editable again, not
even while **Send the rest** has it ``queued``: its content, its batch, and its
schedule stay as they were, **Cancel** refuses it with *This email has started
sending.*, and ``DELETE`` refuses it.  Anything that queues a started email again
(**Send the rest** here, a retry of failed copies later) relies on this rule to
keep the record of what went intact.  Every change to the content or the batch,
and **Send** itself, goes through the function inside a transaction, so a change
and the sender's claim of the same email never overlap.


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
it is then, walking the batch in surname order: ``skip_reason(account, seen,
opt_outs=...)`` asks, in order, whether the account is deleted, deactivated,
without an address, with an address no mail server would take, or with an address
that bounced, whether the person has turned the email's type off (*Opted out of
<type>*), and then whether ``seen`` already holds the address, trimmed and
case-folded.  ``batch.type_opt_outs`` reads the type's opt-outs once for the whole
batch (``apps.mail.types.opted_out_user_ids``), and is ``None`` while the email has
no type, which skips nobody for that reason; an opt-out of a type that no longer
allows one does not apply.  So an address that bounced, or an opt-out made, after
somebody was added shows as skipped at once, and two accounts sharing one address
get one copy, the first in surname order.

Every add goes through ``batch.add_accounts``, which takes the people as a list of
accounts and records one ``BatchAdd``: ``add_filters`` gives it the accounts the
filters choose, a saved group's add the group's people, and **Duplicate** the
people it copies.  An add not made with filters keeps a ``label`` of its own, such
as ``Group: Board``, which ``batch.add_name`` prefers to the filters' words, so the
batch says which group brought each person in even after the group is renamed or
deleted.

Every email has a type before it is sent (``BulkEmail.email_type``, see
:doc:`api-email-types`): ``PATCH`` takes one the caller may send
(``apps.mail.types.sendable_types``), and ``drafts.queue`` refuses an email with none,
or with one whose senders no longer include the caller's roles.


The sender
==========

``job.run_sender`` is one run of the sender.  ``manage.py send_bulk_emails`` calls
it every minute, from ``caldart-bulk-email.timer`` (:ref:`deploy-bulk-email`),
and ``POST /system/bulk-email/run`` calls it from the Scheduled page's **Run now**.

A run may be given a time budget.  **Run now** gives it
``REQUEST_BUDGET_SECONDS`` (45), inside the web server's and the proxy's 60-second
limit on a request: once the budget is spent the run claims nothing more and
stops before its next copy, leaving that email ``sending`` for the next timer run
to finish, and a retry wait that would take it past the budget leaves the copy
``pending`` rather than failing it.  The result says how many copies are left.
The timer's runs have no budget.

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

Before it starts an email the claim checks once more that the sender may send its
type, with the sender's roles as they are now against the type's ``sender_roles``
(``apps.mail.types.sendable_types``): **Send** checked them, but a role can be taken
away, or the type's senders changed, while a send is scheduled.  An email whose
sender's account has been deleted, or who may no longer send the type, is not sent.
One that never started goes back to a draft, its batch and content intact and its
schedule cleared; one **Send the rest** queued again goes back to ``stopped``, its
queued copies with it.  Either way ``not_sent_reason`` keeps the sentence the Drafts
screen and the compose screen show, such as *This email was not sent: you can no
longer send Mission email. Choose another type and send again.*, a WARNING
``bulk_email.refused`` audit line names the email under the ``command`` actor with
the reason ``type_not_sendable``, ``sender_deleted``, or ``no_type``, and the claim
moves on to the next due email.  Queuing the email again clears ``not_sent_reason``.

The pending rows are then sent in surname order, one copy each.  Right before each
copy goes, after its pause, the run reads the person's opt-out of the email's type
afresh (``apps.mail.types.is_opted_out``): one made during a long paced send, or
between **Stop** and **Send the rest**, is honored, the row becomes ``skipped`` with
*Opted out of <type>*, and ``skipped_count`` grows.  After a copy is
handed to the mail server its row is saved first, ``sent`` with its
``Message-ID``, and only then the email's counts, all outside any transaction, so a
run that dies after the hand-over leaves the copy marked sent and the next run does
not send it again.  The run reads ``stop_requested`` afresh before each copy's
pause and again after it.  A **Stop** takes effect there: every copy not yet sent
becomes ``stopped``, and one ``bulk_email.stop`` audit line names who pressed it.
A stop that arrives after the last copy has nothing to keep back: the email is
``sent``, its ``stopped_by`` is cleared, and no stop is recorded.  When no row is
pending, the email is ``sent`` and ``sent_at`` set.

A copy that fails in a way the mail server did not report, an exception other than
a refusal, is a bug: it is logged with its traceback, the copy becomes ``failed``
with *Unexpected error*, and the run leaves that email ``sending`` and moves on to
the next one, so one bad email cannot hold every later one back.  The next run
resumes the email from its next copy.

``manage.py send_bulk_emails`` prints the run's counts and one line per email by its
id, such as ``bulk_email 7: sent 37, failed 1``, and never a name or an address,
since the lines go to the journal.

.. _bulk-email-pacing:

Pacing and refusals
-------------------

The sender sends at most ``BULK_EMAIL_RATE_PER_MINUTE`` copies a minute: after a
copy begins it sleeps out whatever is left of 60 / rate seconds before the next,
so the rate is a ceiling however fast the mail server answers.  The pace is the
run's, carried from one email to the next, so several small emails due together
are paced as one stream.  It opens one mail
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

The message is HTML from the portal's rich text editor, sanitized on every save
and again whenever a copy is built.  ``render.render_copy(bulk, recipient)``
returns a ``RenderedCopy``: the subject, the plain-text and HTML bodies, and a
dictionary of extra headers, with the recipient's field values filled in
(:ref:`api-bulk-email-rich-text`).  The bodies are rendered from
``emails/bulk_email.{txt,html}``: the plain-text body is the message as plain text
(``richtext.html_to_text``) followed by the house footer, and the HTML one puts the
sanitized message inside the shared report frame.  Just before it tries a copy the
sender reads the person's values for the fields the message uses
(``render.fill_values``) and stores them on the row as ``values``, and
``render_copy`` builds the copy from those, so any copy can be rebuilt exactly as
it went.  The sender hands
the finished bodies to ``send_templated`` through the pass-through pair
``emails/bulk_email_copy.{txt,html}``, which print the ``text`` and ``html`` they
are given unchanged, and passes the copy's ``headers`` through
``send_templated``'s ``headers`` argument.

The footer and the headers follow the email's type (:ref:`email-unsubscribe`).  For
a type recipients may turn off, both bodies end with ``unsubscribe.footer_for``'s line
and the recipient's own unsubscribe link, and the copy carries
``unsubscribe.headers_for``'s ``List-Unsubscribe`` and ``List-Unsubscribe-Post``
headers.  For a type they may not, the footer says why the recipient receives it and
there is no header.  A row whose account is gone gets neither, nor does an email with
no type, which cannot be sent; both fall back to the general line *You receive this
email as a member or a friend of <organization>.*


Reusing what was written
========================

CalDART management keeps two things to use again, both shared by every manager and
both outside any one email, so deleting one changes no email.

**Templates.**  ``EmailTemplate`` holds a message: a subject, a message (sanitized as
a draft's is, by the same ``checked_subject`` and ``checked_body`` checks the
draft's serializer uses), and optionally a type and a Reply-To address.
``templates.apply_template`` copies it into a draft through ``drafts.update``, so the
edit rule and a queued email's checks apply; the type comes too only when the
caller may send it.  **Save as a template** on the compose screen is a plain
``POST /bulk-email/templates`` of the draft's words, once its autosave has caught up.

**Recipient groups.**  ``RecipientGroup`` is ``fixed`` (``RecipientGroupMember``
rows) or ``live`` (``RecipientGroupFilter`` rows).  ``groups.group_accounts`` is the
one answer to who a group holds now: a fixed group's accounts, or everybody a live
group's sets choose through ``batch.selected_accounts``, as an add would, combined
in one query.  ``groups.add_group`` hands that to ``batch.add_accounts``, so
duplicates, the row lock, and a queued email going back to a draft work as for any
add.  ``groups.save_group`` turns a batch into a group: the accounts, or the filters
of its adds (a live group added contributes its own sets), refusing a live group
when an add has no filters behind it.

**Duplicate.**  ``templates.duplicate`` makes a fresh ``BulkEmail`` for the caller
with the subject, message, and type, and with ``copy_recipients`` passes the
original's accounts to ``batch.add_accounts`` as one add labeled
``Copied from "<subject>"``.  The rows are fresh and ``batched``, so the skip
reasons are worked out as they are now; the original's rows and counts are not
read for anything else.

Extending
=========

The pieces a feature added to bulk email changes, and where:

* A new **skip reason**, such as a limit to one DART, goes in
  ``batch.skip_reason``, as the type's opt-out does, which both the batch screen and the freeze
  read, so the reason shows in the batch the moment it applies and is stored
  when the send starts.
* A new **field of the email**, such as a ``Reply-To``, is a model
  field, a field of ``BulkEmailUpdateSerializer`` (``PATCH`` saves whatever that
  serializer validates through ``drafts.update``), and a check in ``drafts.queue``
  when **Send** must refuse without it, as ``email_type`` has.
* Anything that changes **what a copy says**, such as a Reply-To, goes in
  ``render_message`` (``render_copy`` passes it the type's footer and adds the
  type's headers) and in the arguments the sender passes to ``send_templated``.  A
  new **recipient field** is one more ``Field`` in ``fields.FIELDS``, which the
  **Insert field** menu, the checks, and the copies all read.
* A new **screen** joins the Bulk Email group of the portal's menu
  (``frontend/src/portal/nav.ts``), its route goes in
  ``frontend/src/portal/routes/bulk-email.tsx``, and its guide page under
  ``docs/user/bulk-email/``.
