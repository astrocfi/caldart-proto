==========
Bulk email
==========

CalDART management writes one email to many members and friends at once: a
newsletter, a seminar notice, a call for volunteers.  A DART leader does the same
for the members and friends of their own DART (:ref:`bulk-email-dart-limit`).  The email is a draft on the
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
    ``render_copy``, ``render_for``, and ``render_message``: one recipient's copy,
    its subject, its two bodies, and its headers; ``check_message``, what a
    token-bearing message is refused for; ``fill_values``, a person's values for the
    fields it uses.
``reply_to.py``
    Where replies go: the default ``Reply-To`` for a sender, the address an email's
    copies carry, and why an address cannot be one.
``checks.py``
    The checks before a send: the errors that stop it and the warnings that do not.
``links.py``
    The link check, held to its deadlines, that never reaches into a private network
    or this server.
``throttling.py``
    The per-account limit on running the checks.
``tests_send.py``
    **Send me a test**: one copy of an email to its sender alone.
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
``senders.py``
    Who may send to whom: ``sender_context``, everyone for CalDART management and
    one DART for a DART leader, and ``dart_limit``, the DART one email may go to.
``delivery.py``
    What became of the copies after they went: a later bounce tied back to its
    copy, **Retry failed**, one person's copy as it went, and hiding an email
    from **Messages**.
``archive.py``
    The **Messages** page: the bulk emails a person received, each as their own
    copy.
``api/``
    The endpoints: ``drafts.py``, ``batch.py``, ``history.py``, ``sender.py``
    (**Run now**), ``sender_context.py`` (``GET /bulk-email/sender``),
    ``richtext.py`` (the field catalog and image uploads), ``preview.py``,
    ``checks.py`` (the checks and the test copy), ``delivery.py`` (retry, a copy,
    hide), and ``archive.py`` (``/messages``), with the shared serializers in
    ``serializers.py``.
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
    **Send** checks the email can go (:ref:`bulk-email-checks`), stores the
    ``Reply-To`` its copies will carry, and sets ``start_at``: now plus
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

Every email has a type before it is sent (``BulkEmail.email_type``, see
:doc:`api-email-types`): ``PATCH`` takes one the caller may send
(``apps.mail.types.sendable_types``), and ``drafts.queue`` refuses an email with none,
or with one whose senders no longer include the caller's roles.


.. _bulk-email-dart-limit:

One DART
--------

A DART leader's email goes to one DART: the one on the sender's member profile, read
as it is at that moment, never stored as the rule.  ``senders.dart_limit(bulk)`` is
``None`` for CalDART management's email (and for one whose sender's account is
gone, which the sender refuses anyway) and a ``DartLimit`` for anybody else's, whose
``dart`` is ``None`` when the sender's profile names no DART or the sender holds
neither bulk email role any more.  The limit is the email's, not the caller's, so
CalDART management changing a leader's email stays inside the leader's DART.

It applies in three places, each reading the same function.  ``batch.add_filters``
forces the add's ``dart`` filter to the DART's id and refuses any other value; an
email limited to no DART refuses every add.  ``batch.skip_reason`` takes the limit
and skips anybody whose profile is not in the DART with *Not in your DART*, right
after a deleted account, so the batch screen shows it at once and the freeze stores
it.  And ``drafts.queue`` refuses an email limited to no DART, as the background
sender's claim does; the claim also returns unsent an email whose batch the limit
leaves nobody in, and the send loop checks the limit again before every copy (both
under *The sender*, below).  ``senders.sender_notice`` names
the sender of an email limited to no DART, for the compose screen and the refusals.  ``BulkEmail.dart`` records the DART the email goes to when the
draft is made, at each add and **Send**, and when the send starts; the lists show
it, and once the email has started it is the DART it went to.


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
So is the email of a DART leader whose profile names no DART any more
(:ref:`bulk-email-dart-limit`), with *This email was not sent: your profile names no
DART, so there is nobody to send to. Set your DART on My profile and send again.*, and
one that has never started whose leader's DART changed so that nobody in the batch is
in it, with *Your DART changed, so this email was not sent. Add the people again and
send when it is ready.*, rather than a send that ends with no copy and no word why.
One that never started goes back to a draft, its batch and content intact and its
schedule cleared; one **Send the rest** queued again goes back to ``stopped``, its
queued copies with it.  Either way ``not_sent_reason`` keeps the sentence the Drafts
screen and the compose screen show, such as *This email was not sent: you can no
longer send Mission email. Choose another type and send again.*, a WARNING
``bulk_email.refused`` audit line names the email under the ``command`` actor with
the reason ``type_not_sendable``, ``sender_deleted``, ``no_type``, ``no_dart``, or
``dart_changed``, and the claim moves on to the next due email.  Queuing the email again clears ``not_sent_reason``.

The pending rows are then sent in surname order, one copy each.  Right before each
copy goes, after its pause, the run reads afresh whether the person is still in the
DART a DART leader's email is limited to (the person's profile and the sender's, as
they are then) and the person's opt-out of the email's type
(``apps.mail.types.is_opted_out``): a change made during a long paced send, between
**Stop** and **Send the rest**, or before a run that died is resumed, is honored, the
row becomes ``skipped`` with *Not in your DART* or *Opted out of <type>*, and
``skipped_count`` grows.  After a copy is
handed to the mail server its row is saved first, ``sent`` with its
``Message-ID``, and only then the email's counts, all outside any transaction, so a
run that dies after the hand-over leaves the copy marked sent and the next run does
not send it again.  The counts are added to in the database (``F() + 1``) rather
than written from the email held in memory, so a bounce moved off ``sent_count``
while the email sends (`After the send`_) stays moved.  The run reads ``stop_requested`` afresh before each copy's
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

``render.render_for(bulk, user, values)`` is one person's whole copy, footer and
headers included: ``render_copy`` builds a row's copy through it with the row's
stored values, the preview builds each person's with their values as they are
now, and a test copy the sender's own, so all three read alike.  The preview's is
inert (``inert=True``): its footer reads as the copy's, but its unsubscribe link
carries ``render.PREVIEW_STAND_IN`` where a signed token goes and it has no headers,
so showing a person's copy to a sender never hands over a link that would turn that
person's email off.  The test copy carries the sender's own real link.  Above the footer
every copy but a test copy carries *View this email in your browser*, a link to the
email on the recipient's **Messages** page, ``<SITE_URL>/portal/messages/<id>``
(``render.browser_url``; `After the send`_).  The footer and the headers follow the
email's type (:ref:`email-unsubscribe`).  For
a type recipients may turn off, both bodies end with ``unsubscribe.footer_for``'s line
and the recipient's own unsubscribe link, and the copy carries
``unsubscribe.headers_for``'s ``List-Unsubscribe`` and ``List-Unsubscribe-Post``
headers.  For a type they may not, the footer says why the recipient receives it and
there is no header.  A row whose account is gone gets neither, nor does an email with
no type, which cannot be sent; both fall back to the general line *You receive this
email as a member or a friend of <organization>.*


.. _bulk-email-reply-to:

Where replies go
----------------

Every copy comes ``From`` ``DEFAULT_FROM_EMAIL``, an address nobody reads, so that
SPF, DKIM, and DMARC align; a reply reaches a person only through the ``Reply-To``
header, which ``send_templated``'s ``reply_to`` argument sets.  ``BulkEmail.reply_to``
is the address the sender chose, and blank means the default,
``reply_to.default_reply_to``: ``BULK_EMAIL_REPLY_TO`` (:doc:`configuration`), or
the sender's own address when that setting is blank.  A fresh draft starts with the
default filled in, which the compose screen's **Reply-To** field shows for the
sender to keep or change.  ``reply_to.reply_to_for`` is the address an email's
copies carry; **Send** stores it on the email.  A queued email can still be changed,
its ``Reply-To`` blanked among it, so the sender resolves and checks it once more
as it claims the email (``reply_to.claimed_reply_to``): when nothing usable
resolves, the copies fall back to ``DEFAULT_FROM_EMAIL``'s address and a WARNING
names the email.  The address settled on is stored on the email, so the Sent detail
shows what the copies went with whatever the setting says later.  An address that is blank or not valid is an error of the
checks, below, so **Send** and a test both refuse it.


.. _bulk-email-checks:

The checks
==========

``checks.run_checks(bulk)`` lists what is wrong with an email as it is saved, each
finding a ``Finding(code, level, message)``.  The compose screen's **Check and
send** card runs them when it opens, again on **Check again**, and again just
before it opens the confirmation, and keeps **Send** off while one is an error.
The codes and their wording are in :ref:`api-bulk-email-checks`.

An **error** stops the send: a blank subject, a message that reads as no text, a
token that cannot be filled in (``render.check_message``), and a ``Reply-To`` that
is blank or not valid.  ``checks.error_findings`` gives those alone, and
``checks.refuse_on_errors`` raises ``ChecksFailedError`` with them, which
``drafts.queue`` calls once the fields it names itself have passed, and the test
copy calls first.  The send endpoint answers that error as a 400 with the findings
under ``checks``.

A **warning** is worth a look, and the sender may send past it: a recipient field
empty for more than half the people who receive the email (counted with
``fields.values_for`` over ``batch.batch_rows``, and only for a field written at
least once without a fallback), placeholder text left in, pictures without a
description or wider than ``BULK_EMAIL_IMAGE_MAX_WIDTH``, and links.  Only the
warnings read the network, so the send, which needs only the errors, never fetches
a link.

Checking a link
---------------

``apps.bulk_email.links`` checks the links: each distinct ``http`` or ``https`` link,
at most 20 a run, is fetched from the server with ``httpx``'s async client, 10 at once,
on an event loop of its own: a ``HEAD``, and a ``GET`` when that answers 400 or more,
since some sites refuse ``HEAD`` alone; the body is never read.  A link to this site
itself, or whose address holds a recipient field, is not fetched.

Every deadline is a real one.  Each request has 5 seconds to connect and for each
read, and each link's whole check, its name lookups, redirects, and second try
included, is canceled at 12 seconds (``asyncio.wait_for``), however slowly a server
drips its answer: *This link timed out.*  The whole run is held to 30 seconds, after
which every link still out reads *This link was not checked in time*.  A name lookup
cannot be canceled, so lookups run in a thread pool the run abandons rather than
waits for.  ``POST /bulk-email/{id}/checks`` is throttled per account,
``BULK_EMAIL_CHECKS_THROTTLE_RATE`` (:doc:`configuration`), so nobody can have the
server fetch addresses without end.

The check must never become a way into the server's own network, so it does its
own name resolution and connects only where it checked:

* ``links.resolve`` asks for every address the host resolves to, and the link is
  refused, *Links into a private network are not checked*, when any of them is not
  on the public internet (``links.is_public``: private, loopback, link-local,
  multicast, reserved, unspecified, shared, IPv6 site-local ``fec0::/10``, or an
  IPv6 address mapping such an IPv4 one), or is one of this server's own addresses
  (``links.own_addresses``: those of ``SITE_URL``'s host and of the machine's own
  names).  A host that answers with one public and one private address is refused,
  since a connection could reach either.
* Only ports 80 and 443 are fetched; a link to any other port reads *Links to a port
  other than 80 or 443 are not checked*.
* The request then goes to the first address checked, with the link's host in the
  ``Host`` header and, for ``https``, as the name TLS sends and verifies the
  certificate against (``httpx``'s ``sni_hostname`` extension).  The host is never
  resolved a second time, so a name whose answer changes between the check and the
  connection cannot lead the request inside.
* Redirects are followed by hand, at most 5, and each hop is resolved and checked
  the same way, its port included, before anything connects to it.
* The client reads no proxy from the environment (``trust_env=False``), which would
  otherwise carry the request past the pinned address.

What a check reports is coarse on purpose, so it cannot serve to probe a host: a
link *does not load*, *timed out*, or was answered with a 4xx or a 5xx error, never
the exact code.  A link that fails is a warning, never an error: a site that is down
for a minute should not stop a newsletter.  For the same reason the compose screen
opens the confirmation even when the checks fail or have not answered within a few
seconds, saying *The checks could not run. You can still send.*: the send refuses
an error on its own.

.. _bulk-email-test-copy:

The test copy
=============

``tests_send.send_test(bulk, actor=...)`` is **Send me a test**.  It refuses an
email the checks find errors in, then mails the actor one copy of the email as it
is saved, built with ``render.render_for`` from the actor's own field values, so it
carries the actor's footer and unsubscribe link, the type's headers, and the
email's ``Reply-To``, exactly as a copy to the actor would; only the subject
differs, starting ``[Test]``.  The copy goes through ``send_templated`` under the
purpose ``bulk_email_test`` (:doc:`email`), so Sent Emails lists it, and touches
nothing of the send: no row joins the batch, and no count moves.  Every call sends
one more copy.  A mail server that refuses it raises ``MailRefusedError``, which the
endpoint answers with a 503.


After the send
==============

The sender records each copy's immediate answer.  ``delivery.py`` joins the later
picture to it, and ``archive.py`` lets every recipient read the email again; the
endpoints are under :ref:`api-bulk-email-delivery` and :ref:`api-bulk-email-messages`.

**Bounces.**  ``BulkEmailConfig.ready`` connects ``delivery.on_email_log_saved`` to
every save of a ``mail.EmailLog``.  When the bounce check (:ref:`email-bounces`)
marks a row of the ``bulk_email`` purpose ``bounced``, the receiver finds the
recipient row with the same ``message_id`` (indexed) that still reads ``sent``,
marks it ``bounced`` with the report's detail as its reason, and moves one from
``sent_count`` to ``bounced_count``.  The mail app never imports this one: the
receiver lives here, and so does the link each copy's row on the Sent Emails page
carries to its bulk email, which ``ready`` registers with ``apps.mail.links``.

**Retry failed.**  ``delivery.retry_failed`` takes a ``sent`` email whose copies
include ``failed`` ones, puts those back to ``pending`` and out of
``failed_count``, records a ``BulkEmailRetry``, and queues the email to start now,
the path **Send the rest** takes.  The email keeps its ``started_at``, so it stays
read-only (:ref:`the edit rule <bulk-email-edit-rule>`), and the sender's own checks
apply to the retried copies as to any: the sender's right to send the type at the
claim, and each person's opt-out before their copy.  A stopped email sends the rest
first; its failed copies can be retried once it has finished.

**A copy as it went.**  ``delivery.recipient_copy`` rebuilds one tried copy with
``render.render_copy`` from the row's stored ``values``.  So does the archive, for
the reader's own row.  Neither ever reads the account's values as they are now.

**Messages.**  ``archive.messages_for`` lists the emails with a row naming the reader
that reads ``sent`` or ``bounced``, not hidden from the archive, newest copy first;
``archive.message_for`` opens one, and anything else is a 404.  Every copy links to
its page there (``render.view_url``, on ``SITE_URL``), and CalDART management can
hide an email from every recipient's list (``delivery.set_hidden``) without changing
its history.


Extending
=========

The pieces a feature added to bulk email changes, and where:

* A new **skip reason** goes in ``batch.skip_reason``, as the type's opt-out and
  the DART limit do, which both the batch screen and the freeze read, so the reason
  shows in the batch the moment it applies and is stored when the send starts.
* A new **field of the email**, as ``reply_to`` is, is a model field, a field of
  ``BulkEmailUpdateSerializer`` (``PATCH`` saves whatever that serializer validates
  through ``drafts.update``), and a check in ``drafts.queue`` when **Send** must
  refuse without it, as ``email_type`` has, or an error in ``checks.error_findings``
  when the reason belongs on the compose screen's checks too, as the ``Reply-To``'s
  has.
* A new **check** is a function in ``checks.py`` answering findings, called from
  ``run_checks``; an error belongs in ``error_findings``, so the send and the test
  refuse it as well, and anything that reads the network must stay a warning.
* Anything that changes **what a copy says** goes in ``render_message``
  (``render_for`` passes it the type's footer and adds the type's headers) and in
  the arguments the sender and the test copy pass to ``send_templated``, as the
  ``Reply-To`` is.  A
  new **recipient field** is one more ``Field`` in ``fields.FIELDS``, which the
  **Insert field** menu, the checks, and the copies all read.
* A new **screen** joins the Bulk Email group of the portal's menu
  (``frontend/src/portal/nav.ts``), its route goes in
  ``frontend/src/portal/routes/bulk-email.tsx``, and its guide page under
  ``docs/user/bulk-email/``.
