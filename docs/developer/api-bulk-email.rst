.. _api-bulk-email:

===============
API: bulk email
===============

The bulk email endpoints under ``/api/v1/bulk-email``, from ``apps.bulk_email``,
hold a bulk email from its draft to its last copy: the draft's message, its batch
of people built from the member list's filters, the send that queues it, and its
results.  Nothing is sent in a request: the background sender sends
(:doc:`bulk-email`).  The portal's Bulk Email screens read them: Compose at
``/bulk-email/compose``, the compose screen of one email at
``/bulk-email/compose/{id}``, **Drafts and scheduled**, **Sent**, **Templates**,
**Recipient groups**, and **Callouts**.  What CalDART management keeps to use again
lives here too: saved templates (:ref:`api-bulk-email-templates`) and saved recipient
groups (:ref:`api-bulk-email-groups`); so do mission callouts
(:ref:`api-bulk-email-callouts`).  The
``/messages`` endpoints, under :ref:`api-bulk-email-messages`, are every signed-in
person's own: the bulk emails they received, read on the portal's **Messages** page.
:doc:`api-reference` covers the conventions these endpoints share: session
authentication, the CSRF header, and the error shapes.

Every endpoint here is the ``management`` role's (*CalDART management*) and the
``dart_leader`` role's (``IsBulkSender``), and a ``system_admin`` passes as always.
Any other role is refused with **403**, and an anonymous caller with **401**.
``POST /system/bulk-email/run`` is the system administrator's alone, and ``POST
/bulk-email/{id}/hide`` CalDART management's alone; ``GET /messages`` and ``GET
/messages/{id}`` answer every signed-in caller.  A caller
reaches the emails ``apps.bulk_email.drafts.visible_to`` gives them, which for
CalDART management is every email, whoever its sender, and for a DART leader the
emails they are the sender of; any other id is **404**.  So a DART leader retries the
failed copies of their own emails alone.  A DART leader also *reads* another sender's
email that went to the DART on the leader's own profile, once it has started
(``apps.bulk_email.senders.readable_by``): ``GET /bulk-email/{id}``, its ``batch``,
``batch.csv``, ``recipients.csv``, and each copy, so the leaders of one DART share a
callout's delivery report; and may **Stop** such an email when it is a mission callout,
whose reminders any of them may start.  Every other action on it is **404** for them.

CalDART management sends to any member or friend.  A DART leader sends only to the
DART on their own member profile (:ref:`api-bulk-email-dart-leaders`).

A refusal that comes from the email's state, such as a change to an email that
has started sending, is **409** ``{"detail": <sentence>}``.  A refusal of the
input is **400** keyed by the field.


The email
=========

``POST /bulk-email/drafts``
---------------------------

Opens a draft for the caller.  The caller's oldest empty draft (no subject, no
message, nobody in its batch) is handed back with **200**; without one a fresh
draft is made, with the caller as its sender, and answered with **201**.  Either
way the body is the email, as ``GET /bulk-email/{id}`` answers it, recording the
DART a DART leader sends to.  No body is taken.  A DART leader whose profile names
no DART is **403** *Your profile names no DART, so there is nobody to send to. Set
your DART on My profile.*, and no draft is made.

``GET /bulk-email/drafts``
--------------------------

Every ``draft`` and ``queued`` email the caller may open that has never started
sending, the most recently edited first.  Unpaginated: a sender keeps a handful.

.. code-block:: json

   [{"id": 9,
     "subject": "Spring newsletter",
     "email_type_name": "Operational",
     "not_sent_reason": "",
     "status": "queued",
     "sender": "Grace Holloway",
     "dart_name": "",
     "created_at": "2026-04-05T09:00:00-07:00",
     "updated_at": "2026-04-05T09:40:00-07:00",
     "start_at": "2026-04-07T08:00:00-07:00",
     "scheduled": true,
     "started_at": null,
     "sent_at": null,
     "stopped_at": null,
     "stop_requested": false,
     "sent_count": 0,
     "failed_count": 0,
     "skipped_count": 0,
     "batch_count": 41,
     "remaining": 0}]

``sender`` is the sender's display name, blank once the account is deleted.
``dart_name`` is the name of the DART a DART leader's email is recorded as going to,
as of the last add, **Send**, or the start of the send, and blank for CalDART
management's email.  ``email_type_name`` is the name of the email's type (:doc:`api-email-types`), blank
while none is chosen.  ``not_sent_reason`` is the sentence the background sender
left on an email it returned unsent because its sender may no longer send its type
(:doc:`bulk-email`), blank otherwise and once the email is queued again.
``batch_count`` is how many people are in the batch, and ``remaining`` how many
copies are waiting to be sent.

``GET /bulk-email/sent``
------------------------

Every email the caller may open that has started sending, the most recently
started first, in the shape ``GET /bulk-email/drafts`` answers: ``sending``,
``sent``, and ``stopped`` emails, and a ``queued`` one **Send the rest** queued
again.
Unpaginated: a handful are sent a month.

``GET /bulk-email/{id}``
------------------------

One email, with everything the compose and Sent screens show:

.. code-block:: json

   {"id": 9,
    "subject": "Spring newsletter",
    "body": "<p>Dear {first_name|friend},</p><p>Join us at <strong>Livermore</strong>.</p>",
    "email_type": 1,
    "email_type_name": "Operational",
    "not_sent_reason": "",
    "reply_to": "operations@caldart.org",
    "default_reply_to": "operations@caldart.org",
    "status": "sending",
    "sender": "Grace Holloway",
    "sender_id": 3,
    "dart_name": "",
    "sender_notice": "",
    "created_at": "2026-04-05T09:00:00-07:00",
    "updated_at": "2026-04-07T08:00:41-07:00",
    "start_at": "2026-04-07T08:00:00-07:00",
    "scheduled": true,
    "confirm_count": null,
    "started_at": "2026-04-07T08:00:02-07:00",
    "sent_at": null,
    "stopped_at": null,
    "stopped_by": "",
    "stop_requested": false,
    "sent_count": 12,
    "failed_count": 0,
    "skipped_count": 1,
    "bounced_count": 0,
    "retried_count": 0,
    "retries": [],
    "hidden_from_archive": false,
    "is_callout": false,
    "closes_at": null,
    "can_edit": false,
    "batch_count": 41,
    "receiving_count": 40,
    "batch_skipped_count": 1,
    "remaining": 28,
    "estimated_finish_at": "2026-04-07T08:01:37-07:00",
    "confirm_above": 50,
    "undo_seconds": 120,
    "message_html": "<!doctype html>\n<html lang=\"en\">..."}

``email_type`` is the id of the email's type and ``email_type_name`` its name; a
fresh draft has none, ``null`` and blank.  ``dart_name`` is the DART a DART leader's
email goes to, blank for CalDART management's: while the email can still change it
is the sender's DART as it is now, and once it has started sending the DART it went
to.  ``sender_notice`` is blank unless the email can still change and its sender is
a DART leader whose profile names no DART, when it reads *This email belongs to
<name>, whose profile names no DART, so nobody can be added.*, naming the sender, for
whoever opens it; the compose screen shows it in place of the filters.  ``reply_to``
is where replies to the email go, blank for ``default_reply_to``, the default for
its sender (:ref:`bulk-email-reply-to`): a fresh draft starts with the default filled
in, and once **Send** has queued the email ``reply_to`` is the address its copies
carry.  ``body`` is the message as sanitized HTML, its recipient field tokens as written
(:ref:`api-bulk-email-rich-text`).  ``message_html`` is the whole HTML email as the
history shows it: the message inside the house email layout, with its tokens as
written rather than filled in.  ``status`` is ``draft``, ``queued``, ``sending``, ``sent``, or ``stopped``
(:ref:`choices-bulk-email-status`); ``can_edit`` is true for a draft or a queued
email that has never started sending (:ref:`the edit rule <bulk-email-edit-rule>`).
``start_at`` is when a queued email starts and ``scheduled`` whether the sender
chose it.  ``batch_count``, ``receiving_count``, and ``batch_skipped_count`` count
the batch as ``GET /bulk-email/{id}/batch`` does.  ``remaining`` counts the copies
waiting to be sent, and ``estimated_finish_at`` is now plus ``remaining`` at
``BULK_EMAIL_RATE_PER_MINUTE``, while the email is ``sending``, and null
otherwise.  ``stopped_by`` is who pressed **Stop**.  Each count counts the rows
of that result: ``bounced_count`` the copies the bounce check later found refused,
which ``sent_count`` then no longer counts (:ref:`api-bulk-email-delivery`).
``retries`` lists each press of **Retry failed**, oldest first, as
``{"id", "requested_at", "requested_by", "count"}`` (``requested_by`` a display name,
blank once the account is deleted), and ``retried_count`` adds up their counts.
``hidden_from_archive`` is true while the email is kept off its recipients'
**Messages** page.  ``is_callout`` is true for a mission callout, whose answers close
at ``closes_at``, and ``closes_at`` is null for any other email
(:ref:`api-bulk-email-callouts`).  ``confirm_above`` is
``BULK_EMAIL_CONFIRM_ABOVE`` and ``undo_seconds`` is ``BULK_EMAIL_UNDO_SECONDS``,
which the screen's confirmation and countdown read.  The portal reads this every
three seconds while the email is ``queued`` or ``sending``.

``PATCH /bulk-email/{id}``
--------------------------

Saves the fields given; any may be left out.

.. code-block:: json

   {"email_type": 1,
    "subject": "Spring newsletter for {first_name}",
    "reply_to": "marin-dart@example.org",
    "body": "<p>Dear {first_name|friend},</p><p>Join us at <strong>Livermore</strong>.</p>"}

``reply_to`` is any valid email address, trimmed, or blank for the default; an
address Django's ``validate_email`` refuses is **400** ``{"reply_to": ["Enter a
valid email address."]}``.

``is_callout`` true makes the email a mission callout: its answers close two days
ahead, rounded up to the half hour, unless ``closes_at`` is given too, and its type
becomes Mission when the caller may send that type.  False makes it an ordinary email
again.  ``closes_at`` is when a callout's answers close, a time given without an
offset read in the site's time zone; it is ignored for an email that is not a callout,
and a time not after now is **400** ``{"closes_at": ["Choose a time in the
future."]}``.  A queued callout cannot be changed so that its answers would close
before it starts: **400** keyed ``closes_at``, worded as **Send** words it.

``email_type`` is the id of a type the caller may send (``GET
/email-types/sendable``); any other is **400** *You cannot send <type> email. Choose
another type.*, and an id no type carries is DRF's *Invalid pk* message.  Choosing
a type changes who the batch skips, since everybody who has turned it off is.

``subject`` is at most 200 characters, one line, and free of control characters,
since the mail library refuses them in a header; ``body`` is HTML of at most
100,000 characters, as the editor writes it, and is stored sanitized
(:ref:`api-bulk-email-rich-text`), so what ``GET`` answers may differ from what was
sent.  Both may be blank while the email is a draft, and both are trimmed.  **200**
with the email.  A refused field is **400**: ``subject`` reads *A subject is one
line.* (for any character ``str.splitlines`` breaks on, from a carriage return to
U+2028), *A subject cannot carry control characters such as tabs.* (for any other
character in Unicode's ``Cc`` category), DRF's length message, or the refusal of a
token that cannot be filled in; ``body`` reads DRF's length message or the refusal
of a token that cannot be filled in: an unknown one, *{nickname} is not a recipient
field. ...* (``fields.unknown_token_message``), or one split by formatting, *{first_name}
has formatting or an angle bracket inside its braces, so it cannot be filled in.
Delete it and put it in again with Insert field.*  The words already saved stay
saved.
A queued email can still be changed, and keeps its ``start_at``, but it cannot be
left without a subject or a message: blanking one is **400** *Write a subject.* or
*Write the message.*, as **Send** refuses it.  A different ``email_type`` takes a
queued email back to a draft instead, its ``start_at``, ``scheduled``, and
``confirm_count`` cleared, as a change to its batch does, since who is skipped as
opted out follows the type; one ``bulk_email.cancel`` audit line with the reason
``type_changed`` says so, and the answer's ``status`` reads ``draft``.  Once the email has started sending
the answer is **409** *This email has been sent and cannot be changed.*

``POST /bulk-email/{id}/duplicate``
-----------------------------------

**Duplicate**: a fresh draft copied from the email, sent or not, which is left as it
is.

.. code-block:: json

   {"copy_recipients": true}

The draft is the caller's own, made afresh even when the caller has an empty draft
already, with the email's ``subject``, ``body`` (its images are links, so they come
too), and ``reply_to``, and its ``email_type`` when the caller may send that type, else
none.  It records the DART the caller may send to, as ``POST /bulk-email/drafts``
does: a DART leader duplicates only their own emails (any other id is **404**), their
copy goes to their own DART alone, and one whose profile names no DART is **403**
with *Your profile names no DART, so there is nobody to send to. Set your DART on My
profile.*
A mission callout's copy is a callout too, ``is_callout`` true, with no answers and
its answers closing two days ahead (:ref:`api-bulk-email-callouts`).
``copy_recipients`` may be left out, and is false then: the batch starts empty.
True copies everybody in the email's batch whose account still exists as one add
labeled ``Copied from "<subject>"``, each a fresh ``batched`` row with the account's
details as they are now, so who is skipped is worked out afresh; in a DART leader's
copy everybody outside their DART is skipped as ``Not in your DART``.  **201** with the
draft, as ``GET /bulk-email/{id}`` answers it.

``DELETE /bulk-email/{id}``
---------------------------

Deletes a draft with its batch: **204**.  A queued email is **409** *Only a draft
can be deleted. Cancel the send first.*, and a started one **409** *This email has
been sent and cannot be changed.*


The batch
=========

The batch is the people the email goes to.  Each **Add to batch** runs the member
list's filters and adds everybody they choose who is not in it yet.  Whether each
person receives a copy is worked out from the account as it is whenever the batch
is read, and once more when the send starts.

Who the filters choose
----------------------

The filters are ``MemberAdminFilterSet``'s, the filter set of
``GET /admin/members`` (:doc:`api-members`), over the same queryset: every member
and friend, never a donor.  An add takes the member list's filters by name:
``kind``, ``search``, ``status``, ``certificate``, ``medical``, ``dart``,
``county``, ``role``, and ``expiring_within``, with the values the list takes.  A
blank value narrows nothing, so a filter bar may send every key.  The list's own
``include_inactive`` is not one of them: deactivated accounts are always added, and
always skipped.  Nor is ``ordering``, which sorts the list and chooses nobody: it
is refused as any unknown name is.

A DART leader's email adds only inside the sender's DART, whoever presses **Add to
batch** (:ref:`api-bulk-email-dart-leaders`).

Who is skipped
--------------

``apps.bulk_email.batch.batch_rows`` walks the batch in surname order, then first
name, then address, with the rows of deleted accounts last, and sets aside
everybody who cannot be sent a copy, asking in this order:

=========================  ==================================================
Reason                     When
=========================  ==================================================
``Account deleted``        the account is gone; the row keeps its name and
                           address
``Not in your DART``       the email is a DART leader's and the person's
                           profile is not in the sender's DART as it is now
``Account deactivated``    ``is_active`` is false
``No email address``       the address is blank
``Invalid email address``  Django's ``validate_email`` refuses the address
``Address bounced``        ``email_bounced_at`` is set: the bounce check
                           matched a permanent failure to the address
                           (:doc:`email`); it is cleared when the address
                           changes or is verified, or by **Clear bounce**
``Opted out of <type>``    the person has turned the email's type off and
                           the type allows that (:doc:`api-email-types`);
                           nobody is skipped for this before a type is
                           chosen
``Duplicate address``      an earlier person in that order has the same
                           address once trimmed and case-folded
=========================  ==================================================

Everybody else receives a copy.  The account table already refuses two addresses
equal but for case, so a duplicate needs stray spaces as well.

``GET /bulk-email/{id}/batch``
------------------------------

The batch's counts, its adds in the order they were pressed, and everybody in it
in the order above:

.. code-block:: json

   {"count": 2,
    "receiving": 1,
    "skipped": 1,
    "adds": [{"id": 4, "label": "Kind: Friends only, County: Marin, Napa",
              "filters": {"kind": "friend", "county": "Marin,Napa"},
              "group": null, "added_count": 2, "already_count": 0,
              "created_at": "2026-04-05T09:10:00-07:00"}],
    "rows": [{"id": 31, "user_id": 12, "name": "Ann Able",
              "email": "ann@example.org", "kind": "friend",
              "dart_name": "Marin DART", "added_by": 4, "status": "batched",
              "will_receive": true, "reason": "", "tried_at": null},
             {"id": 32, "user_id": 40, "name": "Gil Gone",
              "email": "gil@example.org", "kind": "friend",
              "dart_name": "", "added_by": 4, "status": "batched",
              "will_receive": false, "reason": "Account deactivated",
              "tried_at": null}]}

An add's ``label`` is its filters in words, as the member list's filter bar names
them: a kind as the filter bar offers it (*Members only*, *Friends only*), a DART by
its name, a role by its label, a choice by the filter's label for
it, and ``Everybody`` for an add with no filter.  An add that was not made with
filters keeps the name it was given then: ``Group: Board`` for a saved group
(``group`` is its id, null once the group is deleted), and ``Copied from "Spring
newsletter"`` for the people **Duplicate** copied.  A row's ``name``, ``email``,
``kind``, and ``dart_name`` are its own, taken when the person joined the batch
and brought up to date when the send starts; ``user_id`` is null once the account
is deleted.  ``added_by`` is the add's id.  While the email has not started, every
row is ``batched`` and its ``reason`` is worked out now; once it has, each row
carries its stored status (:ref:`choices-bulk-email-recipient-status`) and
reason, and ``tried_at`` says when its copy was tried.  The Sent page reads its
results table from here.

``POST /bulk-email/{id}/batch/add``
-----------------------------------

Adds everybody the filters choose who is not in the batch yet, by account:

.. code-block:: json

   {"filters": {"kind": "friend", "county": "Marin,Napa"}}

``filters`` may be left out, or empty, to add every member and friend, or, for a DART
leader's email, everybody in the DART.  **200** with what the add did:

.. code-block:: json

   {"added": 12, "already_present": 3, "count": 41}

``added`` people joined the batch, ``already_present`` were in it already, and the
batch now holds ``count``.  Each add is kept as a ``BatchAdd`` with the filters that
carried a value.  An add to a ``queued`` email takes it back to a draft, its
``start_at``, ``scheduled``, and ``confirm_count`` cleared, since the count the
sender confirmed no longer holds; so does a removal or a clear.  A refused filter is **400** under ``filters``: *Not a filter of
the member list.* for a name the list does not have, or the list's own message for
a value it refuses, such as ``{"filters": {"kind": ["Select a valid choice. donor
is not one of the available choices."]}}``.  For a DART leader's email, a ``dart``
other than the sender's DART's id, a DART's name included, is **400**
``{"filters": {"dart": ["You can only send to your own DART."]}}``.  Once the email
has started sending the answer is **409**, and so is an add to the email of a DART
leader whose profile names no DART, with the sentence ``sender_notice`` carries.

``DELETE /bulk-email/{id}/batch/{rid}``
---------------------------------------

Takes one person out of the batch: **204**.  A row of another email's batch is
**404**, and an email that has started sending is **409**.

``DELETE /bulk-email/{id}/batch``
---------------------------------

Empties the batch, its adds included: **200** with the empty batch, as
``GET /bulk-email/{id}/batch`` answers it.  An email that has started sending is
**409**.

``GET /bulk-email/{id}/batch.csv``
----------------------------------

The batch as a CSV download, ``caldart-bulk-email-<id>-recipient-list.csv``, in the order
above, with the columns ``Name``, ``Email``, ``Kind``, ``DART``, ``Membership
status`` (the account's now, blank once it is deleted), ``Chosen by`` (the add's
label), ``Will receive`` (``Yes`` or ``No``), ``Reason``, and ``Email type`` (the
email's type, blank while none is chosen).


Sending
=======

``POST /bulk-email/{id}/send``
------------------------------

**Send** and **Schedule for later**: queues the email.  Nothing is sent in the
request.

.. code-block:: json

   {"confirm_count": 52, "start_at": null}

The email must have a type the caller may send, a subject, and a message whose sanitized HTML reads as some
text, every recipient field token in both must be one that can be filled in (as a
save checks it), and somebody in its batch must receive a copy.  When more than ``BULK_EMAIL_CONFIRM_ABOVE`` people receive it,
``confirm_count`` must be that number, the count the sender typed; at or below
the threshold it may be left out.  ``start_at`` is when to start: left out or null
for the end of the undo window, now plus ``BULK_EMAIL_UNDO_SECONDS``, or a time
after now and within a year.  A time given without an offset, such as
``"2026-04-07T08:00"``, is read in the site's time zone.

**200** with the email, now ``queued`` with its ``start_at``, ``scheduled``, and
``confirm_count`` (null below the threshold).  Sending a queued email again
reschedules it.  A refusal is **400** keyed by the field:

- ``subject``: *Write a subject.*, or the refusal of a token, as a save words it.
- ``body``: *Write the message.*, also for a message of empty paragraphs, or the
  refusal of a token, as a save words it.
- ``email_type``: *Choose a type.* when none is chosen, or *You cannot send <type>
  email. Choose another type.* when the type's senders no longer include the
  caller's roles.
- ``batch``: *Nobody in the batch can receive this email. Add people to the
  batch.*, or, for a DART leader's email whose sender's profile names no DART,
  *This email belongs to <name>, whose profile names no DART, so nobody can be
  added.*, naming the sender.
- ``confirm_count``: *Type the number of people this email goes to.* when it is
  missing, or *The batch has changed: it now holds 52 people. Type the new
  count.* when it does not match.
- ``start_at``: *Choose a time in the future.* or *Choose a time within a year.*
- ``closes_at``: *Answers would close before the email goes out. Choose a later time
  under Answers close.* for a mission callout whose answers close by the time it
  would start.

Past those, an error the checks find (:ref:`api-bulk-email-checks`) that the fields
above do not already name, such as a ``Reply-To`` address that is not valid, is
**400** with every error under ``checks``, in the shape ``POST
/bulk-email/{id}/checks`` answers:

.. code-block:: json

   {"checks": [{"code": "reply_to", "level": "error",
                "message": "Replies would go to operations, which is not a valid email address. Change the Reply-To address under What it says."}]}

Warnings never stop a send, and the send fetches no link.  A queued email keeps
the ``Reply-To`` its copies will carry in ``reply_to``: the one it names, or the
default as it is at that moment.  The background sender resolves it once more as
the send starts, and falls back to ``DEFAULT_FROM_EMAIL``'s address when nothing
usable resolves (:ref:`bulk-email-reply-to`).

An email that has started sending is **409**.  One ``bulk_email.queue`` audit line
names the caller, the email, the number of recipients, and whether it was
scheduled.

``POST /bulk-email/{id}/cancel``
--------------------------------

Takes a queued email back to a draft, its batch and content intact, with no
``start_at``: **200** with the email.  A draft is answered unchanged.  Once the
sender has ever started it, **409** *This email has started sending.*, which
includes an email **Send the rest** queued again.  Any CalDART management member
may cancel, not only the sender; a DART leader cancels their own.  One ``bulk_email.cancel``
audit line names the caller.

``POST /bulk-email/{id}/stop``
------------------------------

Asks a send in progress to stop: **200** with the email, ``stop_requested`` true
and ``stopped_by`` the caller.  The sender stops before its next copy: every copy
not yet sent becomes ``stopped`` with the reason *Stopped by* and the caller's
name, and the email ``stopped``.  A ``queued`` email **Send the rest** queued
again stops at once the same way.  Any other email is **409** *This email is not
sending.*  One ``bulk_email.stop`` audit line names the caller and the copies kept
back, written when the stop takes effect; a stop that arrived after the last copy
had gone records nothing, and the email reads ``sent``.

``POST /bulk-email/{id}/resume``
--------------------------------

**Send the rest** of a stopped send.  Every ``stopped`` row is checked again first,
as **Retry failed** checks a failed one (``POST /bulk-email/{id}/retry``): it takes
its account's name and address as they are now, and a deleted or deactivated account,
a missing, invalid, or bounced address, an opt-out of the type, a person outside a
DART leader's DART, or, in a callout's reminder round, a person who has answered since
makes it ``skipped`` with that reason.  The rest go back to
``pending`` and the email is queued to start now, with no undo window.  **200** with
the email.  Nobody already sent a copy is sent another.  The email keeps its
``started_at``, so it stays read-only (:ref:`the edit rule <bulk-email-edit-rule>`).
An email that is not ``stopped`` is **409** *Only a stopped email can send the
rest.*  One ``bulk_email.resume`` audit line names the caller, the number of copies
queued again, and the number skipped.

``GET /bulk-email/{id}/recipients.csv``
---------------------------------------

One send's results as a CSV download, ``caldart-bulk-email-<id>-recipients.csv``,
in the order the send went, with the columns ``Name``, ``Email``, ``Kind``,
``DART``, ``Result`` (the row's status in words: ``Sent``, ``Failed``,
``Skipped``, ``Not sent (stopped)``, ``Not sent yet``, ``On the list``, or
``Bounced``), ``Reason``, ``Tried at`` (when the copy was last tried,
``MM/DD/YYYY at h:mm AM`` in the site's time zone, blank when it never was), and
``Email type``.  This is the delivery report the Sent page shows.

``POST /system/bulk-email/run``
-------------------------------

Runs the bulk email sender once, in the request, as one run of the timer does: it
finishes any email left ``sending``, then starts and sends every queued email whose
``start_at`` has come (:doc:`bulk-email`), but for at most 45 seconds, inside the
proxy's limit on a request.  An email still going then is left ``sending`` for the
timer's next run.  ``system_admin`` only.  No body
is taken; there is no dry run, because the sender sends only what CalDART
management has already pressed **Send** on.

.. code-block:: json

   {"busy": false,
    "emails": 1,
    "sent": 1,
    "failed": 1,
    "skipped": 2,
    "out_of_time": false,
    "remaining": 0,
    "actions": [
      {"kind": "sent", "member": "Ann Able", "email": "ann@example.org",
       "on": null, "amount_cents": null, "detail": "Spring newsletter"},
      {"kind": "failed", "member": "Bea Bell", "email": "bea@example.org",
       "on": null, "amount_cents": null, "detail": "Refused by the mail server"}]}

``busy`` is true when another run of the sender was working, and this one then
did nothing.  ``emails`` counts the emails worked on, ``sent`` and ``failed`` the
copies tried, and ``skipped`` the people set aside as each email started.
``out_of_time`` is true when the 45 seconds ran out with copies still to send, and
``remaining`` counts them.  Each action is one copy: ``kind`` is ``sent`` or ``failed``, and ``detail`` the subject
or the reason.  One ``bulk_email.run`` audit line names the caller
and the counts.


.. _api-bulk-email-dart-leaders:

DART leaders
============

A DART leader sends bulk email to the members and friends of one DART: the DART on
their own member profile.  The ``dart_leader`` role names no DART of its own, so a
leader whose profile names none has nobody to send to, and when a leader's profile
DART changes, the people their emails reach change with it from then on.
``apps.bulk_email.senders`` holds the rule: ``sender_context`` says what one account
may send to, and ``dart_limit`` what one email may go to, which is its sender's,
whoever is working on it, so CalDART management changing a leader's email stays
inside that DART too.  The server keeps the limit whatever the client sends:

- every add to a leader's email has its ``dart`` filter forced to the sender's
  DART, and refuses any other;
- anybody in the batch whose profile is not in the sender's DART is skipped with
  *Not in your DART*, so a person who moves to another DART after being added, or a
  row that reached the batch any other way, receives nothing;
- **Send** refuses the email of a leader whose profile names no DART, and the
  background sender checks again when it starts the send, returning the email unsent
  when the leader's DART has changed so that nobody in the batch is in it, and again
  before every copy, so **Send the rest** and a resumed run skip anybody outside the
  DART as it is then (:doc:`bulk-email`);
- a leader reaches only their own emails, by any id.

The types a leader may send are the ones whose senders name ``dart_leader``
(``GET /email-types/sendable``): Operational and Mission as the site starts.

``GET /bulk-email/sender``
--------------------------

Who the caller may send to.  **200**:

.. code-block:: json

   {"is_management": false,
    "can_send": true,
    "reason": "",
    "dart": 4,
    "dart_name": "Marin",
    "default_reply_to": "office@caldart.org"}

``is_management`` is true for CalDART management and a system administrator, who
send to everyone, with ``dart`` null and ``dart_name`` blank.  For a DART leader
``dart`` and ``dart_name`` are the DART on their profile.  ``can_send`` is false for
a leader whose profile names no DART, and ``reason`` then says *Your profile names no
DART, so there is nobody to send to. Set your DART on My profile.*; it is blank
otherwise.  The compose screen shows that sentence in place of the form, and names a
leader's DART as a fixed value in place of the DART filter; the Drafts and scheduled
screen shows it too.  ``default_reply_to`` is where replies to the caller's email go
when they choose no Reply-To address: ``BULK_EMAIL_REPLY_TO``, or the caller's own
address when that setting is blank.  The template form names it under its
**Reply-To** field.


.. _api-bulk-email-checks:

Checking before sending
=======================

The compose screen's **Check and send** card lists what the checks find in an email
before it goes, and **Send me a test** mails the sender a copy of it
(:ref:`bulk-email-checks`).

``POST /bulk-email/{id}/checks``
--------------------------------

What the checks find in the email as it is saved.  No body is taken.  **200** with
every finding, the errors first; an empty list when there is nothing to say:

.. code-block:: json

   [{"code": "empty_field", "level": "warning",
     "message": "{dart_name} is empty for 41 of 120 people who receive this email, so their copies show nothing there. Add words to show instead, as in {dart_name|other words}, or take it out."},
    {"code": "link_broken", "level": "warning",
     "message": "This link does not load (the site answered with a 4xx error): https://caldart.org/old-page"}]

``level`` is ``error`` for a finding that stops the send and ``warning`` for one
the sender may send past.  ``code`` names the kind:

==================  ========  ========================================================
Code                Level     When
==================  ========  ========================================================
``no_subject``      error     the subject is blank: *Write a subject.*
``no_body``         error     the message reads as no text: *Write the message.*
``unfillable``      error     a token in the subject or the message cannot be filled
                              in, worded as a save refuses it
``reply_to``        error     the ``Reply-To`` the copies would carry is blank or not
                              a valid address
``empty_field``     warning   a recipient field, written without a fallback at least
                              once, is empty for more than half the people who
                              receive the email, counted with their values now
``placeholder``     warning   the subject or the message still says ``TODO``,
                              ``XXX``, ``lorem ipsum``, or ``[insert``, case ignored
``image_alt``       warning   pictures with no description (``alt``), counted
``image_wide``      warning   pictures wider than ``BULK_EMAIL_IMAGE_MAX_WIDTH``, by
                              the ``width`` the message gives them or the width an
                              upload was stored at, counted
``link_insecure``   warning   a link that does not use ``https``
``link_broken``     warning   a link answered with a 4xx or a 5xx error, named by
                              that class alone, one that times out, and one that
                              cannot be reached or keeps redirecting: *does not load*
``link_private``    warning   a link into a private network or to this server: *Links
                              into a private network are not checked*
``link_unchecked``  warning   a link to a port other than 80 or 443, and one not
                              answered before the run's 30 seconds ran out
``links_skipped``   warning   more than 20 links: only the first 20 were checked
==================  ========  ========================================================

The empty-field check is skipped while a token cannot be filled in.  The links are
the message's distinct ``http`` and ``https`` links, in the order written, less any
to this site itself (``SITE_URL``'s host and port) and any whose address holds a
recipient field; ``mailto:`` links are not checked.  Each is fetched from the
server, so the answer can take several seconds, and at most about 30
(:ref:`bulk-email-checks`).  The endpoint is throttled per account under
``BULK_EMAIL_CHECKS_THROTTLE_RATE`` (30 a minute unless :doc:`configuration` says
otherwise); past it the answer is **429**.

``POST /bulk-email/{id}/test``
------------------------------

**Send me a test**: mails the caller one copy of the email as it is saved, filled in
with the caller's own field values, and built as the background sender builds a
copy, its footer, unsubscribe headers, and ``Reply-To`` included; only the subject
differs, starting ``[Test]``.  No body is taken.  **200**:

.. code-block:: json

   {"to": "pat@example.org"}

``to`` is the caller's own address, the only one a test goes to.  Every call sends
one more copy.  A test adds nobody to the batch and counts toward nothing; it is in
the email log under the purpose ``bulk_email_test`` (:doc:`email`), naming the
caller's account.  An email the checks find errors in is **400** with the errors
under ``checks``, as ``send`` answers it, and nothing is sent.  A mail server that
refuses the copy is **503** ``{"detail": "The mail server refused the test. Try
again in a minute."}``; the failed send is in the email log, and the refusal is
logged on ``caldart.mail``.


.. _api-bulk-email-delivery:

The delivery report
===================

A copy the relay accepted can still come back: the bounce check reads delivery
reports hours or days later (:ref:`email-bounces`).  ``apps.bulk_email.delivery``
joins that later picture to the send.  Every save of an email log row of the
``bulk_email`` purpose reaches a ``post_save`` receiver, and a row that reads
``bounced`` marks the recipient row that went out with the same ``Message-ID``, if it
still reads ``sent``, as ``bounced``, its ``reason`` the report's ``bounce_detail``
(or *The receiving mail server refused it* when the report gave none), and moves the
email's count from ``sent_count`` to ``bounced_count``.  A row already ``bounced`` is
left alone, so a report read twice counts once.  The counts are moved in the
database, and the sender adds to its own counts there too, so a bounce read while
the email is still sending is not undone by the next copy's count.

``POST /bulk-email/{id}/retry``
-------------------------------

**Retry failed**.  Each ``failed`` copy first takes its account's name and address
as they are now, so an address corrected since is the one used, and is asked
``batch.skip_reason`` afresh: a deleted account (*Account deleted*), a deactivated
one, a missing, invalid, or bounced address, an opt-out of the type, or an address
already sent this round of the email makes the row ``skipped`` with that reason and adds
to ``skipped_count``.  For a mission callout the rows are taken the latest round first,
and a failed copy whose person a later round's copy reached, or is going to, or one
already queued in this retry, is ``skipped`` with *Sent a later copy instead*, so a
person whose first copy and reminder both failed is sent one copy, the reminder.  A
failed reminder (``round`` above 0) whose person has answered the callout since is
``skipped`` with *Answered the callout*.  Every other failed copy goes back to
``pending`` with its reason cleared.  All of them leave ``failed_count``.  The email is queued to start now, with
no undo window, as **Send the rest** queues it.  No body is taken.  **200** with the
email, ``queued`` with the retry in ``retries``.  The background sender then sends
those copies alone, each filled in with the person's values as they are then, and
checks once more that the sender may send the type and that nobody has turned it
off.  A bounced copy is not retried, since its address is bad, nor a skipped one.
Nobody already sent a copy of that round is sent another, nobody is sent an earlier
round's copy once a later one has gone to them, and nobody is queued twice.  The email keeps its ``started_at``, so it stays
read-only, and **Stop** stops the retry as it stops **Send the rest**.  A refusal is
**409**:

- *This email has not been sent.* for an email that never started;
- *This email was stopped. Send the rest first, then retry the failed copies.* for a
  ``stopped`` one;
- *This email is still sending. Retry the failed copies once it has finished.* for
  one ``queued`` or ``sending``;
- *No copy failed, so there is nothing to retry.*
- *Nobody whose copy failed can be sent one now. Each is marked skipped, with the reason
  on their line.* when every failed copy was skipped; the skips are kept, and nothing is
  queued.

Each retry that queued a copy is kept as a ``BulkEmailRetry``
(:ref:`data-model-bulk-email`).  One ``bulk_email.retry`` audit line names the caller,
the copies queued, and the people skipped.  When the retried copies have all been
tried the email is ``sent`` again with its first ``sent_at`` kept, and one
``bulk_email.retry_finished`` line takes the place of a second ``bulk_email.send``.

``GET /bulk-email/{id}/recipients/{rid}/copy``
----------------------------------------------

One person's copy as it went, rebuilt by ``render.render_copy`` from the ``values``
stored on the row when the copy was last tried, never from the account as it is now.
``rid`` is a row of the email, of any round.  **200**:

.. code-block:: json

   {"id": 31,
    "name": "Ann Able",
    "email": "ann@example.org",
    "status": "sent",
    "tried_at": "2026-04-07T08:00:02-07:00",
    "subject": "Spring newsletter for Ann",
    "html": "<!doctype html>\n<html lang=\"en\">...",
    "text": "Dear Ann,\n\nJoin us at Livermore.\n\n--\n..."}

The copy is for the caller, not its recipient, so it is inert as the preview is
(``render_copy``'s ``inert``): the footer keeps its words, but its unsubscribe link
carries ``render.PREVIEW_STAND_IN`` where a signed token goes, and no token that could
turn the recipient's email off is in either body.  The message ``GET /bulk-email/{id}`` answers as
``message_html`` carries nobody's link either.  A row of another email is **404**, and a
row whose copy was never tried (skipped, stopped, or not sent yet) **409** *This person
was not sent a copy.*

``POST /bulk-email/{id}/hide``
------------------------------

**Hide from Messages** and **Show in Messages**: keeps the email off every
recipient's **Messages** page (:ref:`api-bulk-email-messages`), or puts it back.

.. code-block:: json

   {"hidden": true}

**200** with the email, ``hidden_from_archive`` as asked.  Nothing else changes: the
copies, the counts, and the Sent page read as before.  ``hidden`` is required; left
out it is **400** keyed ``hidden``.  An email that never started is **409** *This
email has not been sent.*  CalDART management's alone, whoever sent the email.  One
``bulk_email.hide`` audit line names the caller and the choice, written when it
changes.


.. _api-bulk-email-messages:

Messages
========

Every signed-in person can read again the bulk emails they were sent, on the
portal's **Messages** page (``/messages``).  ``apps.bulk_email.archive`` answers it.
An email is the reader's when one of its recipient rows names their account and reads
``sent`` or ``bounced``: a skipped, failed, stopped, or unsent copy is not one they
received.  Each is shown as the reader's own copy, filled in from the values stored
on their own row when it went, never from their profile as it is now and never from
anybody else's row.  Only bulk email is here, never a receipt, a reminder, or any
other mail about the person's own account, and there is no way to show an email to
anybody it was not sent to.  An email CalDART management has hidden is neither
listed nor opened.

Every copy's footer links here, *View this email in your browser*, to
``<SITE_URL>/portal/messages/<id>``: ``SITE_URL`` carries any ``URL_PREFIX``, so the
link reaches the portal under it (``render.browser_url``).  The plain-text copy writes
the line *View this email in your browser:* and the address above its footer.

``GET /messages``
-----------------

Every email the caller received, the copy most recently sent to them first, one per
email.  Unpaginated: a few go out a month.

.. code-block:: json

   [{"id": 9,
     "subject": "Spring newsletter for Ann",
     "sent_at": "2026-04-07T08:00:02-07:00",
     "from_name": "Grace Holloway",
     "email_type_name": "Operational",
     "answer_url": ""}]

``id`` is the bulk email's.  ``subject`` is the subject as the caller's copy had it,
``sent_at`` when their copy went, ``from_name`` the sender's display name, or the
organization's name once the sender's account is deleted, and ``email_type_name``
the email's type.  ``answer_url`` is, for a mission callout, the caller's own answer
page, a link signed for them as the buttons in their copy are, which the portal opens
in place of the copy; it is blank for any other email.

``GET /messages/{id}``
----------------------

One email, as the caller's own copy: the fields above, plus ``html``, the whole HTML
email, and ``text``, the plain-text one, as ``render.render_copy`` rebuilds them from
the caller's row, with the caller's own live unsubscribe link, as their email had it.
The portal draws ``html`` in a frame sandboxed to popups that leave the sandbox, with
no scripts, no forms, and no same-origin access, and puts ``<base target="_blank">``
at its head, so the email's links open in a new tab; the Sent page's message and a
copy on the delivery report are drawn the same way.  An email the caller did not receive, and one hidden from Messages,
is **404**.


.. _api-bulk-email-callouts:

Mission callouts
================

A mission callout asks everybody it goes to whether they can fly, and collects the
answers (:ref:`bulk-email-callouts`).  It is written on the compose screen like any
bulk email, with ``is_callout`` set by ``PATCH /bulk-email/{id}``; each recipient's
copy carries three buttons, each a link to the answer page signed for that person.
The endpoints below are the **Callouts** screen's.  A caller reaches the callouts
``apps.bulk_email.callouts.visible_callouts`` gives them: every callout that has
started sending for CalDART management, and for a DART leader the ones they sent and
the ones that went to the DART on their own profile.  ``{id}`` is the bulk email's
id; any other is **404**, a draft callout included.

``GET /bulk-email/callouts``
----------------------------

Every callout the caller may open, the most recently started first.  Unpaginated: a
callout goes out a few times a year.

.. code-block:: json

   [{"id": 12,
     "subject": "Fire near Paradise",
     "status": "sent",
     "sender": "Grace Holloway",
     "dart_name": "",
     "started_at": "2026-08-06T10:00:02-07:00",
     "sent_at": "2026-08-06T10:01:40-07:00",
     "closes_at": "2026-08-08T10:00:00-07:00",
     "closed_at": null,
     "is_open": true,
     "counts": {"reached": 41, "available": 12, "limited": 5,
                "unavailable": 9, "no_answer": 15}}]

``subject`` reads as the sender's own copy would, each recipient field filled in with
the sender's values, or its fallback once the sender's account is gone.  ``sender`` is
blank once the account is deleted, and ``dart_name`` blank for CalDART management's
callout.  ``closes_at`` is when the answers close, ``closed_at`` when
**Close now** closed it sooner, and ``is_open`` whether it takes answers now.
``counts`` counts the people the callout reached by answer: ``reached`` everybody a
copy of any round went to (``sent``, or ``bounced`` afterwards) and anybody who
answered, and ``no_answer`` those of them with no answer.

``GET /bulk-email/callouts/{id}``
---------------------------------

One callout: the list's fields, ``closed_by`` (who pressed **Close now**, blank when
nobody did or the account is deleted), ``closed_skipped`` (how many copies were
skipped with *Callout closed* because the callout had closed before they went),
``reminders``, and ``recipients``, one per person counted in ``reached``, in surname
order:

.. code-block:: json

   {"id": 12,
    "subject": "Fire near Paradise",
    "closed_by": "",
    "closed_skipped": 0,
    "reminders": [{"round": 1, "requested_at": "2026-08-07T09:00:00-07:00",
                   "count": 15}],
    "recipients": [{"user_id": 31, "name": "Ann Able", "email": "ann@example.org",
                    "answer": "limited", "note": "Saturday only",
                    "answered_at": "2026-08-06T11:20:00-07:00",
                    "dart_name": "Marin DART", "home_airport": "LVK",
                    "aircraft": ["N123AB"],
                    "go_no_go": {"membership": true, "medical": true,
                                 "verified": true}}]}

``answer`` is ``available``, ``limited``, or ``unavailable``
(:ref:`choices-callout-answer-kind`), null before the person answers, when ``note`` is
blank and ``answered_at`` null.  ``dart_name``, ``home_airport``, ``aircraft`` (the
N-numbers on the profile), and ``go_no_go`` read the account as it is now;
``go_no_go`` is the member check's own three verdicts (:doc:`api-aircraft`), and the
person is a go when all three hold.  An account since deleted or deactivated is not
listed, nor counted, and neither is its answer.  Each of
``reminders`` is one round of **Remind non-responders**, oldest first: its number, when
its rows were made, and how many reminders it queued, leaving out the people it
skipped.  The portal reads this every half minute while the callout is open.

``GET /bulk-email/callouts/{id}/answers.csv``
---------------------------------------------

The answers as a CSV download, ``caldart-callout-<id>-answers.csv``, one line per
person in the order above, with the columns ``Name``, ``Email``, ``Answer`` (in words,
blank for none), ``Note``, ``Answered at`` (``MM/DD/YYYY at h:mm AM`` in the site's time
zone, blank for none), ``DART``, ``Home airport``, ``Aircraft`` (the N-numbers,
separated by commas), and ``Go/no-go`` (``GO`` or ``NO-GO``).

``POST /bulk-email/callouts/{id}/remind``
-----------------------------------------

**Remind non-responders**: sends the callout again, with the same message, to
everybody the callout reached who has not answered, the people ``recipients`` lists
with a null ``answer``, as a new round of copies.  Somebody whose first copy failed or
was skipped was never reached, and is not reminded.  No body is
taken.  Each person's row of the round takes their name and address as they are now
and is asked ``batch.skip_reason`` afresh, as **Retry failed** asks it, with the
addresses of everybody who has answered counted as already sent: a missing, invalid,
or bounced address, an opt-out of the type,
somebody outside a DART leader's DART, and an address somebody who answered shares
are ``skipped`` with that reason.  The rest are queued, and the email is queued to
start now, with no undo window; the background sender fills each copy in with the
person's values as they are then.  **200** with the callout, the round in
``reminders``.  A refusal is **409**, and nothing changes:

- *This callout has not been sent.* for one that never started;
- *This callout was stopped. Send the rest first, then remind the others.*;
- *This callout is still sending. Remind the others once it has finished.* for one
  ``queued`` or ``sending``;
- *This callout has closed.*;
- *Everybody has answered, so there is nobody to remind.*;
- *Nobody who has not answered can be sent a reminder now: each would be skipped, as
  the delivery report shows why.* when every person left would be skipped.

One ``callout.remind`` audit line names the caller, the round, the reminders queued,
and the people skipped, and one ``callout.remind_finished`` line follows once the
round has gone.  A reminder's copies can be read one by one
(``GET /bulk-email/{id}/recipients/{rid}/copy``), and a failed one is retried by
**Retry failed** like any other.

``POST /bulk-email/callouts/{id}/close``
----------------------------------------

**Close now**: the callout takes no more answers from now, and every answer link reads
*This callout has closed*.  A round of copies queued and not started yet, a round of
reminders or the rest of a stopped send, is called off: each of its copies becomes
``skipped`` with *Callout closed*, and the email reads ``sent`` again.  A round being
sent stops before its next copy, and **Send the rest** afterwards sends nothing: the
background sender skips every copy of a callout whose answers have closed, when it
starts the email and before each copy, so a timer that runs past ``closes_at`` sends
nothing either.  No body is taken.  **200** with the callout, ``is_open``
false and ``closed_at`` and ``closed_by`` set.  A callout already closed, by **Close
now** or by its ``closes_at``, is **409** *This callout has closed.*  One
``callout.close`` audit line names the caller.

The answer page
---------------

``/mail/callout/<token>`` is outside the API: a page in the public site's shell, which
needs no sign-in, served by ``apps.bulk_email.views.callout_answer``.  The token names
the callout and the person, signed with the salt ``bulk_email.callout``, and has no age
limit of its own.

- ``GET`` shows the callout's subject and message as the person's copy had them, the
  three answers, the one ``?answer=available``, ``limited``, or ``unavailable`` names
  chosen (else the person's current answer), a note field, and **Send answer**.  It
  records nothing.
- ``POST`` with ``answer`` and ``note`` (form fields) records the answer, or changes
  the person's earlier one, and answers **200** with the answer as recorded.  No
  answer, or one that is not a kind, is **400** with the form and *Choose one of the
  three answers.*  The view is CSRF-exempt: the signed token is the authorization.
- Once the callout has closed both answer **200** with *This callout has closed.* and
  record nothing, and so do both for an account since deactivated, with *This link no
  longer works*.
- One link may send at most ``CALLOUT_ANSWER_THROTTLE_RATE`` answers (10 an hour
  unless :doc:`configuration` says otherwise); past it a ``POST`` is **429**, says to
  try again later, and records nothing.  A token that was changed, signed for another purpose, or names a
  callout or an account since deleted is **400** with *This link does not work*.

A new answer, or a change of answer, raises the ``callout_answer`` event
(:doc:`notification-events`) and writes one ``callout.answer`` audit line; a change to
the note alone is saved and raises neither, so editing a note emails nobody.


.. _api-bulk-email-rich-text:

Rich text and recipient fields
==============================

The portal's editor writes a message as HTML (:ref:`the editor <architecture-rich-text>`),
and the server trusts none of it: the message is sanitized when it is saved, and
again whenever a copy is built, for a preview or a send.  ``bulk_email.richtext``
and ``bulk_email.fields`` hold what the server does with that HTML,
``bulk_email.render`` builds each copy, and the endpoints below serve the editor and
the preview.

**Sanitizing.**  ``richtext.sanitize`` reduces any HTML to what an email may
carry, with nh3:

- the tags kept are ``p``, ``br``, ``strong``, ``em``, ``b``, ``i``, ``u``,
  ``s``, ``h1``, ``h2``, ``h3``, ``ul``, ``ol``, ``li``, ``a``, ``img``,
  ``blockquote``, and ``hr``.  ``script`` and ``style`` go with everything
  inside them; any other tag goes and the text inside it stays;
- a link keeps ``href`` and ``title``, and an image ``src``, ``alt``, ``width``,
  and ``height``.  Every other attribute goes: ``style``, ``class``, ``id``,
  ``target``, ``rel``, and every event handler such as ``onclick``;
- a link's ``href`` must be an absolute ``http``, ``https``, or ``mailto``
  address, and an image's ``src`` an absolute ``http`` or ``https`` one.  Any
  other address, ``javascript:``, ``data:``, or a relative path among them, is
  removed and leaves the tag without it, since a relative address means nothing
  in a mail program;
- ``width`` and ``height`` must be whole numbers of pixels, and comments are
  removed.

A recipient field's token (below) is plain text to the sanitizer, so it survives
anywhere, a link's address included once the address is absolute:
``https://caldart.org/join?dart={dart_name}`` keeps its token, while a link
whose whole address is ``{email}`` is relative and loses it.

The answer is well formed, and sanitizing it again changes nothing.

**The plain-text part.**  ``richtext.html_to_text`` writes the same message as
plain text: each paragraph and heading a block of its own, blocks separated by
a blank line, a line break a new line; each item of a bulleted list starting
``-`` and of a numbered list its number (``1.``), one to a line, a nested list
indented two spaces; a quotation's lines starting ``>``; a horizontal rule as
``----``; a link as ``text (url)``, or the address alone when the text is the
address; and an image as its description (``alt``).

**Recipient fields.**  A subject or a message can carry a token that each
person's copy fills in with that person's own value.  The catalog,
``fields.FIELDS``, is fixed in the code:

=======================  ===================  =========================================
Token                    Label                Value
=======================  ===================  =========================================
``{first_name}``         First name           the account's first name
``{last_name}``          Last name            the account's last name
``{full_name}``          Full name            first and last name, joined by a space
``{email}``              Email address        the account's address
``{dart_name}``          DART                 the name of the DART on the profile
``{plan}``               Membership plan      the plan behind the membership status
``{membership_status}``  Membership status    ``Current``, ``Expired``, ``Friend``, or
                                              ``Donor``, as the member list shows it
``{expiration}``         Expiration date      when the membership runs out,
                                              ``MM/DD/YYYY``; empty for a lifetime
                                              member, a friend, and a donor
``{home_airport}``       Home airport         the home airport identifier on the
                                              profile, such as ``LVK``
=======================  ===================  =========================================

The status, plan, and expiration are ``members.services.membership_of``'s.
A person with no value for a field, such as an account with no profile and so
no DART, gets an empty value.  A token may name a fallback for an empty value,
``{first_name|friend}``.  A token's name is lower-case letters, digits, and
underscores, starting with a letter, and its fallback is plain text with no
brace, bar, angle bracket, or line break.  Anything else in braces is not a
token and arrives as written, including Django's template syntax: ``{{ x }}``,
``{{x}}``, and ``{% y %}`` are never evaluated, because filling in a token is a
lookup in the catalog (``fields.substitute``), never template rendering.  A
token naming a field the catalog does not have is unknown, and
``fields.unknown_tokens`` lists each one by name, in the order first written.
``fields.values_for`` reads one person's value for each token a message uses,
and ``fields.substitute`` puts them in, HTML-escaping each value for the HTML
part, so a name holding ``<b>`` arrives as text, and replacing an empty value
by the token's fallback.  A value that lands inside a link's ``href`` or an
image's ``src`` is percent-encoded as well, everything but ``@``, and so is a
fallback that stands in for an empty one there, so
``https://caldart.org/darts?name={dart_name}`` works for *Marin & Napa* and
``mailto:{email}`` for an address holding a ``+``.

``{{`` and ``}}`` are never part of a token and are left exactly as written,
inside an address or out; they never stand for a single brace.  A web address
that needs a brace of its own writes it percent-encoded, ``%7B`` and ``%7D``.
``fields.unknown_token_message`` names an unknown token and the ways out: in the
text, *{nickname} is not one of the fields. Pick a field from Insert field, or
take out the braces.*; inside a link's ``href`` or a picture's ``src``
(``fields.is_in_address``), *{id} is not one of the fields. Pick a field from
Insert field, or, if the braces belong in the web address, write them as %7B and
%7D: %7Bid%7D.*


**Checking a message.**  ``render.check_message`` is what a save, a preview, and a
send refuse, by field.  The subject is refused for its first unknown token.  The
message is sanitized, then refused with *This message has formatting nested too
deeply to send. Take out some of the lists, quotations, or styles inside one
another.* when its tags nest more than 32 deep (``richtext.MAX_NESTING_DEPTH``,
far beyond any real message; ``html_to_text`` reads the tags recursively), and
otherwise for its first unknown token in the HTML or in
the plain text derived from it, and for a token the two would not fill in alike:
one the plain text holds but the HTML does not, because formatting splits it
(``<strong>{first</strong>_name}``, which reads ``{first_name}`` as text), or one
in the HTML's text the plain text does not hold, because its fallback holds an
angle bracket.  That one is refused with *{first_name} has formatting or an angle
bracket inside its braces, so it cannot be filled in. Delete it and put it in again
with Insert field.*

**Filling in each copy.**  ``render.render_message(subject, body, values)`` builds
one copy: the message sanitized; the HTML body with each value escaped, and each
value or fallback percent-encoded inside a link's or an image's address, inside
``emails/bulk_email.html``, the house email layout; the plain-text body derived from
that filled-in HTML, so it reads each value as it is and writes a link's address as
the link has it, percent-encoded (``Go (https://e.com/?d=Marin%20County)``), followed
by the house footer from ``emails/bulk_email.txt``; and the subject with each value
as it is, a line break in a value read as a space.  The
preheader is the start of the plain text.  When the sender tries a copy it reads the
person's values for the fields the message uses, as they are at that moment
(``render.fill_values``), and stores them on the row as ``values``, token to value,
such as ``{"first_name": "Pat", "expiration": "04/30/2026"}``; a message that fills
in nothing stores ``{}``, and a deleted account fills every field in empty.
``render.render_copy(bulk, recipient)`` builds a copy from those stored values, so
a copy rebuilt later reads as it went, whatever happened to the profile since, and
puts the link to the email on the recipient's **Messages** page above its footer
(:ref:`api-bulk-email-messages`).  The preview carries that link too, as the copy
will; a test copy carries none, since it is nobody's message.


``GET /bulk-email/fields``
--------------------------

The recipient fields, in the order the **Insert field** menu lists them.
Unpaginated.  **200**:

.. code-block:: json

   [{"token": "first_name", "label": "First name",
     "description": "The person's first name."},
    {"token": "dart_name", "label": "DART",
     "description": "The name of the person's DART."}]

``token`` is the field's name without its braces.


``POST /bulk-email/images``
---------------------------

Stores one image for a message.  The body is multipart form data with the file
under ``image``; any other content type is **415**.  ``bulk_email.images.store``
checks it and keeps it:

- the file must be at most ``BULK_EMAIL_IMAGE_MAX_BYTES`` long (5 MB unless
  :doc:`configuration` says otherwise), or it is refused with *This image is
  larger than 5 MB. Choose a smaller one.*, the limit named in MB;
- it must be a PNG, JPEG, GIF, or WebP image by its content, whatever its name
  says, read with Pillow, or it is refused with *Choose a PNG, JPEG, GIF, or
  WebP image.*, which is also the answer for a file cut short;
- it must hold at most 200 frames, and at most 40 million pixels counted across
  every frame (the canvas times the frame count), or it is refused with *This
  image is too big to use in an email. Choose a smaller one.*.  Both are checked
  from the file's headers before any pixel is decoded, so a few kilobytes of GIF
  holding hundreds of one-pixel frames on a huge canvas costs nothing to refuse.
  A canvas Pillow itself treats as a decompression bomb (over about 89 million
  pixels) gets the same answer;
- an image wider than ``BULK_EMAIL_IMAGE_MAX_WIDTH`` (1200 pixels) is scaled
  down to that width with its proportions kept, an animated one frame by frame;
  a photo is turned upright by its orientation tag; and every image is saved
  afresh in its own format without its comment, EXIF block, XMP, or color
  profile, so a photo's location never reaches a reader;
- the file is stored as ``bulk-email/<uuid>.<ext>`` under ``MEDIA_ROOT``, its
  name a fresh random UUID, with a ``BulkEmailImage`` row naming the caller as
  the uploader (:ref:`data-model-bulk-email`).

**201**:

.. code-block:: json

   {"id": 4,
    "url": "https://caldart.example.org/media/bulk-email/3f2c9e0b8d6a4f7e9a1b2c3d4e5f6a7b.png",
    "width": 1200,
    "height": 600}

``url`` is absolute: ``SITE_URL``'s scheme and host followed by the file's
``MEDIA_URL`` path, which carries any ``URL_PREFIX``.  ``width`` and ``height``
are the stored image's size in pixels.  A missing file is **400**
``{"image": ["No file was submitted."]}``, and a refused one **400** with the
reason under ``image``.

Every copy of an email links to its images by that URL rather than carrying
them, so a send to hundreds of people stays small, and the image must stay
reachable without signing in for as long as a sent email may be read: a mail
program fetches it with no session.  The web server serves ``/media/`` straight
off disk to anybody, and only ``/media/documents/`` is refused
(:doc:`deployment`), so ``/media/bulk-email/`` needs nothing of its own.  In
development Django serves ``/media/`` while ``DEBUG`` is on, which it is under
``make run``.  An image is never deleted by the site.


``POST /bulk-email/{id}/preview``
---------------------------------

One person's copy of the saved message, as it will go.  Nothing is sent or stored.

.. code-block:: json

   {"recipient_id": 12}

``recipient_id`` is a row of the batch, any row, a skipped one included; left out
or null, the copy is the first person's who receives one.  The people stepped
through are those who receive a copy, in the order the send goes.  **200**:

.. code-block:: json

   {"subject": "Spring newsletter for Ann",
    "html": "<!doctype html>\n<html lang=\"en\">...",
    "text": "Dear Ann,\n\nJoin us at Livermore.\n\n--\n...",
    "recipient": {"id": 12, "name": "Ann Able", "email": "ann@example.org"},
    "position": 1,
    "count": 40,
    "previous_id": null,
    "next_id": 13}

``html`` is the whole HTML email and ``text`` the plain-text one, each ending with
the footer as the person's copy reads; for a type recipients may turn off, its
unsubscribe link is inert, the page's address with no signed token
(``render.inert_unsubscribe_url``), so a preview never unsubscribes anyone.  ``position`` is the person's
place, from 1, among the ``count`` people who receive a copy, and
``previous_id`` and ``next_id`` are the rows either side, null at either end.
A copy already tried is filled in with the ``values`` it went out with; any other
with the account's values as they are now.  While nobody in the batch receives a
copy, the preview is the caller's own copy, with ``recipient.id`` null and
``position`` and ``count`` 0.  A token that cannot be filled in is **400** keyed
``subject`` or ``body``, worded as a save words it; a row that is not in the batch
is **400** ``{"recipient_id": ["That person is not in the batch."]}``.


.. _api-bulk-email-templates:

Templates
=========

A template is a message saved under a name, shared by every member of CalDART
management: a subject, a message, and optionally a type and a Reply-To address.
**Start from a template** copies it into a draft, so changing the draft leaves the
template as it was.  The model is ``EmailTemplate`` (:ref:`data-model-bulk-email`).
These endpoints are CalDART management's alone, whatever role sends bulk email.

``GET /bulk-email/templates``
-----------------------------

Every template, by name ignoring case.  Unpaginated: CalDART keeps a handful.

.. code-block:: json

   [{"id": 3,
     "name": "Monthly newsletter",
     "subject": "News for {first_name}",
     "body": "<p>Dear {first_name|friend},</p><p>The hangar is open.</p>",
     "email_type": 1,
     "email_type_name": "Operational",
     "reply_to": "news@caldart.org",
     "created_by": "Grace Holloway",
     "created_at": "2026-04-01T09:00:00-07:00",
     "updated_at": "2026-04-05T10:30:00-07:00"}]

``email_type`` is null and ``email_type_name`` blank for a template with no type,
including one whose type has been deleted.  ``reply_to`` is blank for the default.
``created_by`` is who saved it, blank once that account is deleted.

``POST /bulk-email/templates``
------------------------------

Saves a template, the caller as its author.  ``name`` is required; the rest may be
left out.

.. code-block:: json

   {"name": "Monthly newsletter",
    "subject": "News for {first_name}",
    "body": "<p>Dear {first_name|friend},</p><p>The hangar is open.</p>",
    "email_type": 1,
    "reply_to": "news@caldart.org"}

``name`` is at most 80 characters, trimmed, and must not be another template's in
any mix of cases: **400** *A template named "Monthly newsletter" already exists.
Choose another name.*  ``subject`` and ``body`` follow a draft's rules
(``PATCH /bulk-email/{id}``): the same lengths and refusals, and the message saved
sanitized.  ``email_type`` is a type the caller may send, or null, refused as a
draft refuses it; ``reply_to`` is an address, or blank.  **201** with the template.
One ``email_template.create`` audit line names the caller and the template.

``GET /bulk-email/templates/{id}``
----------------------------------

One template, as the list shows it.

``PATCH /bulk-email/templates/{id}``
------------------------------------

Saves the fields given, each checked as ``POST`` checks it, which is how a template
is renamed and edited; a template may keep its own name in another case.  **200**
with the template, and one ``email_template.update`` audit line.

``DELETE /bulk-email/templates/{id}``
-------------------------------------

Deletes the template: **204**.  Drafts already started from it keep their words.
One ``email_template.delete`` audit line names the caller and the template's id.

``POST /bulk-email/{id}/apply-template``
----------------------------------------

**Start from a template**: fills the email from a template.

.. code-block:: json

   {"template": 3}

The email's ``subject`` and ``body`` become the template's, its ``reply_to`` the
template's or, when the template leaves it blank, the sender's default
(:ref:`bulk-email-reply-to`), and its ``email_type`` the template's when the template
has one the caller may send; otherwise the email keeps its type.  The batch is not touched.  **200** with the email.  An unknown template is
**400** under ``template``.  The change goes through the edit rule, as ``PATCH``
does: an email that has started sending is **409**; a template that changes a queued
email's type takes it back to a draft; and one that would leave a queued email of the
same type without a subject or a message is **400** *Write a subject.* or *Write the
message.*  The portal
asks before it replaces words already written.


.. _api-bulk-email-groups:

Recipient groups
================

A recipient group is a set of people saved under a name, shared by every member of
CalDART management, that **Add a saved group** puts into a batch.  It is one of two
kinds (:ref:`choices <choices-group-kind>`):

``fixed``
    A list of accounts, exactly the people it was saved with until somebody adds or
    removes one.  Deleting an account takes it out.
``live``
    A list of member list filter sets, each as **Add to batch** takes them.  Every use
    runs them afresh, so the group follows membership as it changes: its people are
    everybody any set chooses, deactivated accounts included as an add includes
    them, and nobody while it has no set.

The models are ``RecipientGroup``, ``RecipientGroupMember``, and
``RecipientGroupFilter`` (:ref:`data-model-bulk-email`).  These endpoints are CalDART
management's alone.  A change the group's kind does not allow is **409**
``{"detail": <sentence>}``: *Only a fixed group lists its people. Change a live group
by its filters.* or *Only a live group has filters. Change a fixed group by its
people.*

``GET /bulk-email/groups``
--------------------------

Every group, by name ignoring case.  Unpaginated.

.. code-block:: json

   [{"id": 5,
     "name": "Marin friends",
     "kind": "live",
     "count": 41,
     "needs_fixing": false,
     "filter_sets": [{"id": 8, "label": "Kind: Friends only, County: Marin",
                      "filters": {"kind": "friend", "county": "Marin"},
                      "position": 0, "needs_fixing": false}],
     "created_by": "Grace Holloway",
     "created_at": "2026-04-01T09:00:00-07:00",
     "updated_at": "2026-04-05T10:30:00-07:00"}]

``count`` is how many people the group holds now, a live group's sets run afresh.
``filter_sets`` are a live group's sets in order, each named as an add's filters are;
a fixed group has none.  A set's ``needs_fixing`` is true when the member list no
longer accepts it as stored, such as a ``dart`` whose DART has been deleted; the
group's ``needs_fixing`` is then true and its ``count`` null, and its people, their
CSV, and its add to a batch are refused with *This group's filters need fixing.*
until the set is taken out.  Every other group answers as usual.  ``updated_at`` moves on whenever the group, its people, or
its sets change.

``POST /bulk-email/groups``
---------------------------

Makes an empty group, the caller as its author: ``{"name": "Board", "kind":
"fixed"}``.  ``name`` is at most 80 characters, trimmed, and must not be another
group's in any mix of cases: **400** *A group named "Board" already exists. Choose
another name.*  ``kind`` is ``fixed`` or ``live``.  **201** with the group, and one
``recipient_group.create`` audit line naming the caller, the group, and its kind.

``GET /bulk-email/groups/{id}``
-------------------------------

One group, as the list shows it.

``PATCH /bulk-email/groups/{id}``
---------------------------------

Renames the group (``{"name": "Directors"}``), checked as ``POST`` checks it; a
``kind`` other than its own is **400** *A group's kind cannot change. Save a new
group instead.*  Every add already made keeps the name the group had then.  **200**
with the group, and one ``recipient_group.rename`` audit line.

``DELETE /bulk-email/groups/{id}``
----------------------------------

Deletes the group: **204**.  Every batch the group was added to keeps its people and
its add's name, and the add's ``group`` becomes null.  One ``recipient_group.delete``
audit line names the caller and the group's id.

``GET /bulk-email/groups/{id}/members``
---------------------------------------

Everybody in the group now, in surname order:

.. code-block:: json

   {"count": 1,
    "people": [{"user_id": 12, "name": "Ann Able", "email": "ann@example.org",
                "kind": "friend", "dart_name": "Marin DART", "is_active": true}]}

``kind`` and ``dart_name`` are worked out as a batch row's are; ``is_active`` is
false for a deactivated account, which a send skips.  A live group whose filters need
fixing is **409** *This group's filters need fixing.*, here and for the CSV.

``GET /bulk-email/groups/{id}/members.csv``
-------------------------------------------

The same people as a CSV download named after the group, ``caldart-group-<slug>.csv``
with the slug of its name (``caldart-group-<id>.csv`` for a name with no letter or
digit), with the columns ``Name``, ``Email``, ``Kind``, and ``DART``.

``POST /bulk-email/groups/{id}/members``
----------------------------------------

Adds one account to a fixed group: ``{"user": 12}``.  **201** with the person, as
the list above shows them.  An account that is not a member or a friend is **400**
under ``user`` *Choose a member or a friend.*, and one in the group already *Ann Able
is in this group already.*

``DELETE /bulk-email/groups/{id}/members/{user_id}``
----------------------------------------------------

Takes one account out of a fixed group: **204**, or **404** when it is not in it.

``POST /bulk-email/groups/{id}/filters``
----------------------------------------

Adds a filter set to a live group, after its others: ``{"filters": {"county":
"Napa"}}``, taken and refused as ``POST /bulk-email/{id}/batch/add`` takes them, blank
values dropped; left out or empty it chooses every member and friend.  A set the
group has already is **400** under ``filters`` *This group has these filters
already.*  **201** with the set.

``DELETE /bulk-email/groups/{id}/filters/{fid}``
------------------------------------------------

Takes a filter set out of a live group: **204**, or **404** for a set that is not the
group's.

``GET /bulk-email/groups/people``
---------------------------------

The members and friends to offer while adding somebody to a fixed group:
``?search=able`` runs the member list's own search, by name or address, and answers
at most ten, in surname order, deactivated accounts included; a blank search answers
nobody.

.. code-block:: json

   [{"id": 12, "name": "Ann Able", "email": "ann@example.org"}]

``POST /bulk-email/{id}/batch/add-group``
-----------------------------------------

**Add a saved group**: adds everybody in the group now to the batch, as one add.

.. code-block:: json

   {"group": 5}

Everybody not in the batch yet joins it, as with ``POST /bulk-email/{id}/batch/add``,
and **200** answers the same counts: ``{"added": 12, "already_present": 3, "count":
41}``.  The add links the group and is labeled ``Group: <name>``.  An unknown group is
**400** under ``group``, and so is a live group whose filters need fixing, with
*This group's filters need fixing.*; nothing is added then.  A queued email goes back to a draft, as with any add, and
one that has started sending is **409**.

``POST /bulk-email/{id}/save-group``
------------------------------------

Saves the batch as a group: ``{"name": "Hangar crew", "kind": "fixed"}``, the name
checked as ``POST /bulk-email/groups`` checks it.  **201** with the group, audited as
``recipient_group.create`` like a group made empty.

- A ``fixed`` group holds every account in the batch now, whether or not each will
  receive the email; a deleted account is left out.
- A ``live`` group holds the filters behind the batch, once each, in the order they
  were added: every add's filters, and every live group added, its sets as they are
  now.  People taken out of the batch one by one are not remembered.  A batch with
  people no filters chose, from a fixed group or **Duplicate**, is **400** under
  ``batch``: *Some people in this batch came from a fixed group or were copied from
  another email, so there are no filters to save for them. Save it as a fixed group
  instead.*  One with people from a group since deleted is refused the same way with
  *The group "Board" was deleted, so its filters are gone. Save this batch as a fixed
  group instead.*

An empty batch is **400** under ``batch``: *The batch is empty. Add people to it
before you save it as a group.*
