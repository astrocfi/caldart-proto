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
``/bulk-email/drafts/{id}``, **Drafts & scheduled**, and **Sent**.
:doc:`api-reference` covers the conventions these endpoints share: session
authentication, the CSRF header, and the error shapes.

Every endpoint here is the ``management`` role's (*CalDART management*), and a
``system_admin`` passes as always.  Any other role is refused with **403**, and an
anonymous caller with **401**.  ``POST /system/bulk-email/run`` is the system
administrator's alone.  A caller reaches the emails
``apps.bulk_email.drafts.visible_to`` gives them, which for CalDART management is
every email, whoever its sender; any other id is **404**.

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
way the body is the email, as ``GET /bulk-email/{id}`` answers it.  No body is
taken.

``GET /bulk-email/drafts``
--------------------------

Every ``draft`` and ``queued`` email the caller may open, the most recently
edited first.  Unpaginated: a sender keeps a handful.

.. code-block:: json

   [{"id": 9,
     "subject": "Spring newsletter",
     "status": "queued",
     "sender": "Grace Holloway",
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
``batch_count`` is how many people are in the batch, and ``remaining`` how many
copies are waiting to be sent.

``GET /bulk-email/sent``
------------------------

Every ``sending``, ``sent``, and ``stopped`` email the caller may open, the most
recently started first, in the shape ``GET /bulk-email/drafts`` answers.
Unpaginated: a handful are sent a month.

``GET /bulk-email/{id}``
------------------------

One email, with everything the compose and Sent screens show:

.. code-block:: json

   {"id": 9,
    "subject": "Spring newsletter",
    "body": "Join us at Livermore on Saturday.\n\nBring your logbook.",
    "status": "sending",
    "sender": "Grace Holloway",
    "sender_id": 3,
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
    "can_edit": false,
    "batch_count": 41,
    "receiving_count": 40,
    "batch_skipped_count": 1,
    "remaining": 28,
    "estimated_finish_at": "2026-04-07T08:01:37-07:00",
    "confirm_above": 50,
    "undo_seconds": 120}

``status`` is ``draft``, ``queued``, ``sending``, ``sent``, or ``stopped``
(:ref:`choices-bulk-email-status`); ``can_edit`` is true for the first two.
``start_at`` is when a queued email starts and ``scheduled`` whether the sender
chose it.  ``batch_count``, ``receiving_count``, and ``batch_skipped_count`` count
the batch as ``GET /bulk-email/{id}/batch`` does.  ``remaining`` counts the copies
waiting to be sent, and ``estimated_finish_at`` is now plus ``remaining`` at
``BULK_EMAIL_RATE_PER_MINUTE``, while the email is ``sending``, and null
otherwise.  ``stopped_by`` is who pressed **Stop**.  ``confirm_above`` is
``BULK_EMAIL_CONFIRM_ABOVE`` and ``undo_seconds`` is ``BULK_EMAIL_UNDO_SECONDS``,
which the screen's confirmation and countdown read.  The portal reads this every
three seconds while the email is ``queued`` or ``sending``.

``PATCH /bulk-email/{id}``
--------------------------

Saves the fields given; any may be left out.

.. code-block:: json

   {"subject": "Spring newsletter",
    "body": "Join us at Livermore on Saturday.\n\nBring your logbook."}

``subject`` is at most 200 characters, one line, and free of control characters,
since the mail library refuses them in a header; ``body`` is plain text of at most
20,000 characters, a blank line separating paragraphs.  Both may be blank while
the email is a draft, and both are trimmed.  **200** with the email.  A refused
field is **400**: ``subject`` reads *A subject is one line.* (for any character
``str.splitlines`` breaks on, from a carriage return to U+2028), *A subject cannot
carry control characters such as tabs.* (for any other character in Unicode's
``Cc`` category), or DRF's length message; ``body`` reads DRF's length message.
A queued email can still be changed, and keeps its ``start_at``, but it cannot be
left without a subject or a message: blanking one is **400** *Write a subject.* or
*Write the message.*, as **Send** refuses it.  Once the email has started sending
the answer is **409** *This email has been sent and cannot be changed.*

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
``Account deactivated``    ``is_active`` is false
``No email address``       the address is blank
``Invalid email address``  Django's ``validate_email`` refuses the address
``Address bounced``        ``email_bounced_at`` is set: the bounce check
                           matched a permanent failure to the address
                           (:doc:`email`); it is cleared when the address
                           changes or is verified, or by **Clear bounce**
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
    "adds": [{"id": 4, "label": "Kind: Friend, County: Marin, Napa",
              "filters": {"kind": "friend", "county": "Marin,Napa"},
              "added_count": 2, "already_count": 0,
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
them: a DART by its name, a role by its label, a choice by the filter's label for
it, and ``Everybody`` for an add with no filter.  A row's ``name``, ``email``,
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

``filters`` may be left out, or empty, to add every member and friend.  **200**
with what the add did:

.. code-block:: json

   {"added": 12, "already_present": 3, "count": 41}

``added`` people joined the batch, ``already_present`` were in it already, and the
batch now holds ``count``.  Each add is kept as a ``BatchAdd`` with the filters that
carried a value.  A refused filter is **400** under ``filters``: *Not a filter of
the member list.* for a name the list does not have, or the list's own message for
a value it refuses, such as ``{"filters": {"kind": ["Select a valid choice. donor
is not one of the available choices."]}}``.  Once the email has started sending
the answer is **409**.

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

The batch as a CSV download, ``caldart-bulk-email-<id>-batch.csv``, in the order
above, with the columns ``Name``, ``Email``, ``Kind``, ``DART``, ``Membership
status`` (the account's now, blank once it is deleted), ``Added by`` (the add's
label), ``Will receive`` (``Yes`` or ``No``), and ``Reason``.


Sending
=======

``POST /bulk-email/{id}/send``
------------------------------

**Send** and **Schedule for later**: queues the email.  Nothing is sent in the
request.

.. code-block:: json

   {"confirm_count": 52, "start_at": null}

The email must have a subject and a message, and somebody in its batch who
receives a copy.  When more than ``BULK_EMAIL_CONFIRM_ABOVE`` people receive it,
``confirm_count`` must be that number, the count the sender typed; at or below
the threshold it may be left out.  ``start_at`` is when to start: left out or null
for the end of the undo window, now plus ``BULK_EMAIL_UNDO_SECONDS``, or a time
after now and within a year.  A time given without an offset, such as
``"2026-04-07T08:00"``, is read in the site's time zone.

**200** with the email, now ``queued`` with its ``start_at``, ``scheduled``, and
``confirm_count`` (null below the threshold).  Sending a queued email again
reschedules it.  A refusal is **400** keyed by the field:

- ``subject``: *Write a subject.*
- ``body``: *Write the message.*
- ``batch``: *Nobody in the batch can receive this email. Add people to the
  batch.*
- ``confirm_count``: *Type the number of people this email goes to.* when it is
  missing, or *The batch has changed: it now holds 52 people. Type the new
  count.* when it does not match.
- ``start_at``: *Choose a time in the future.* or *Choose a time within a year.*

An email that has started sending is **409**.  One ``bulk_email.queue`` audit line
names the caller, the email, the number of recipients, and whether it was
scheduled.

``POST /bulk-email/{id}/cancel``
--------------------------------

Takes a queued email back to a draft, its batch and content intact, with no
``start_at``: **200** with the email.  A draft is answered unchanged.  Once the
sender has started it, **409** *This email has started sending.*  Any CalDART
management member may cancel, not only the sender.  One ``bulk_email.cancel``
audit line names the caller.

``POST /bulk-email/{id}/stop``
------------------------------

Asks a send in progress to stop: **200** with the email, ``stop_requested`` true
and ``stopped_by`` the caller.  The sender stops before its next copy: every copy
not yet sent becomes ``stopped`` with the reason *Stopped by* and the caller's
name, and the email ``stopped``.  An email that is not ``sending`` is **409** *This
email is not sending.*  One ``bulk_email.stop`` audit line names the caller.

``POST /bulk-email/{id}/resume``
--------------------------------

**Send the rest** of a stopped send: every ``stopped`` row goes back to
``pending`` and the email is queued to start now, with no undo window.  **200**
with the email.  Nobody already sent a copy is sent another.  An email that is not
``stopped`` is **409** *Only a stopped email can send the rest.*  One
``bulk_email.resume`` audit line names the caller and the number of copies
queued again.

``GET /bulk-email/{id}/recipients.csv``
---------------------------------------

One send's results as a CSV download, ``caldart-bulk-email-<id>-recipients.csv``,
in the order the send went, with the columns ``Name``, ``Email``, ``Kind``,
``DART``, ``Result`` (the row's status in words: ``Sent``, ``Failed``,
``Skipped``, ``Not sent (stopped)``, ``Not sent yet``, ``In the batch``, or
``Bounced``), and ``Reason``.

``POST /system/bulk-email/run``
-------------------------------

Runs the bulk email sender once, in the request, as one run of the timer does:
it finishes any email left ``sending``, then starts and sends every queued email
whose ``start_at`` has come (:doc:`bulk-email`).  ``system_admin`` only.  No body
is taken; there is no dry run, because the sender sends only what CalDART
management has already pressed **Send** on.

.. code-block:: json

   {"busy": false,
    "emails": 1,
    "sent": 1,
    "failed": 1,
    "skipped": 2,
    "actions": [
      {"kind": "sent", "member": "Ann Able", "email": "ann@example.org",
       "on": null, "amount_cents": null, "detail": "Spring newsletter"},
      {"kind": "failed", "member": "Bea Bell", "email": "bea@example.org",
       "on": null, "amount_cents": null, "detail": "Refused by the mail server"}]}

``busy`` is true when another run of the sender was working, and this one then
did nothing.  ``emails`` counts the emails worked on, ``sent`` and ``failed`` the
copies tried, and ``skipped`` the people set aside as each email started.  Each
action is one copy: ``kind`` is ``sent`` or ``failed``, and ``detail`` the subject
or the reason.  The run is paced like any other, so a large send keeps the request
open for as long as it takes.  One ``bulk_email.run`` audit line names the caller
and the counts.
