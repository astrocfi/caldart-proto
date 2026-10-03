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
``/bulk-email/compose/{id}``, **Drafts & scheduled**, and **Sent**.
:doc:`api-reference` covers the conventions these endpoints share: session
authentication, the CSRF header, and the error shapes.

Every endpoint here is the ``management`` role's (*CalDART management*) and the
``dart_leader`` role's (``IsBulkSender``), and a ``system_admin`` passes as always.
Any other role is refused with **403**, and an anonymous caller with **401**.
``POST /system/bulk-email/run`` is the system administrator's alone.  A caller
reaches the emails ``apps.bulk_email.drafts.visible_to`` gives them, which for
CalDART management is every email, whoever its sender, and for a DART leader the
emails they are the sender of; any other id is **404**.

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
whoever opens it; the compose screen shows it in place of the filters.  ``body`` is the message as sanitized HTML, its recipient field tokens as written
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
otherwise.  ``stopped_by`` is who pressed **Stop**.  ``confirm_above`` is
``BULK_EMAIL_CONFIRM_ABOVE`` and ``undo_seconds`` is ``BULK_EMAIL_UNDO_SECONDS``,
which the screen's confirmation and countdown read.  The portal reads this every
three seconds while the email is ``queued`` or ``sending``.

``PATCH /bulk-email/{id}``
--------------------------

Saves the fields given; any may be left out.

.. code-block:: json

   {"email_type": 1,
    "subject": "Spring newsletter for {first_name}",
    "body": "<p>Dear {first_name|friend},</p><p>Join us at <strong>Livermore</strong>.</p>"}

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
them: a kind as the filter bar offers it (*Members only*, *Friends only*), a DART by
its name, a role by its label, a choice by the filter's label for
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

The batch as a CSV download, ``caldart-bulk-email-<id>-batch.csv``, in the order
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

**Send the rest** of a stopped send: every ``stopped`` row goes back to
``pending`` and the email is queued to start now, with no undo window.  **200**
with the email.  Nobody already sent a copy is sent another.  The email keeps its
``started_at``, so it stays read-only (:ref:`the edit rule <bulk-email-edit-rule>`).  An email that is not
``stopped`` is **409** *Only a stopped email can send the rest.*  One
``bulk_email.resume`` audit line names the caller and the number of copies
queued again.

``GET /bulk-email/{id}/recipients.csv``
---------------------------------------

One send's results as a CSV download, ``caldart-bulk-email-<id>-recipients.csv``,
in the order the send went, with the columns ``Name``, ``Email``, ``Kind``,
``DART``, ``Result`` (the row's status in words: ``Sent``, ``Failed``,
``Skipped``, ``Not sent (stopped)``, ``Not sent yet``, ``In the batch``, or
``Bounced``), ``Reason``, and ``Email type``.

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
    "dart_name": "Marin"}

``is_management`` is true for CalDART management and a system administrator, who
send to everyone, with ``dart`` null and ``dart_name`` blank.  For a DART leader
``dart`` and ``dart_name`` are the DART on their profile.  ``can_send`` is false for
a leader whose profile names no DART, and ``reason`` then says *Your profile names no
DART, so there is nobody to send to. Set your DART on My profile.*; it is blank
otherwise.  The compose screen shows that sentence in place of the form, and names a
leader's DART as a fixed value in place of the DART filter.


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
that needs a brace of its own writes it percent-encoded, ``%7B`` and ``%7D``,
and ``fields.unknown_token_message`` says so when a sender writes one bare:
*{id} is not a recipient field. Choose a field from Insert field, or, if the
braces belong in a web address, write them as %7B and %7D: %7Bid%7D.*


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
a copy rebuilt later reads as it went, whatever happened to the profile since.


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

``html`` is the whole HTML email and ``text`` the plain-text one.  ``position`` is
the person's place, from 1, among the ``count`` people who receive a copy, and
``previous_id`` and ``next_id`` are the rows either side, null at either end.
A copy already tried is filled in with the ``values`` it went out with; any other
with the account's values as they are now.  While nobody in the batch receives a
copy, the preview is the caller's own copy, with ``recipient.id`` null and
``position`` and ``count`` 0.  A token that cannot be filled in is **400** keyed
``subject`` or ``body``, worded as a save words it; a row that is not in the batch
is **400** ``{"recipient_id": ["That person is not in the batch."]}``.
