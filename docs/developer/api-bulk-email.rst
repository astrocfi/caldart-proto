.. _api-bulk-email:

===============
API: bulk email
===============

The bulk email endpoints under ``/api/v1/bulk-email``, from ``apps.bulk_email``,
send one email to everybody the member list's filters select, after a preview
that lists them and sends nothing.  The portal's *Bulk Email* screen at
``/admin/bulk-email`` reads them.  :doc:`api-reference` covers the conventions
these endpoints share: session authentication, the CSRF header, and the error
shapes.

Every endpoint here is the ``management`` role's (*CalDART management*), and a
``system_admin`` passes as always.  Any other role is refused with **403**, and
an anonymous caller with **401**.


Who a bulk email reaches
========================

The recipients are chosen by ``MemberAdminFilterSet``, the filter set of
``GET /admin/members`` (:doc:`api-members`), over the same queryset: every
member and friend, never a donor.  ``filters`` takes the member list's filters
by name: ``kind``, ``search``, ``status``, ``certificate``, ``medical``,
``dart``, ``county``, ``role``, and ``expiring_within``, with the values the
list takes.  A blank value narrows nothing, so a filter bar may send every key.
The list's own ``include_inactive`` is not one of them: deactivated accounts
are always looked at, and always skipped.  Nor is ``ordering``, which sorts the
list and chooses nobody: it is refused as any unknown name is.

``bulk_email.services.build_recipients`` walks the accounts in surname order,
then first name, then address, and sets aside everybody who cannot be sent a
copy, with the reason:

=========================  ==================================================
Reason                     When
=========================  ==================================================
``Account deactivated``    ``is_active`` is false
``No email address``       the address is blank
``Invalid email address``  Django's ``validate_email`` refuses the address
``Address bounced``        ``email_bounced_at`` is set: the bounce check
                           matched a permanent failure to the address
                           (:doc:`email`); it is cleared when the address
                           changes or is verified, or by **Clear bounce**
``Duplicate address``      an earlier account on the list has the same
                           address once trimmed and case-folded
=========================  ==================================================

Everybody else is a recipient.  The account table already refuses two addresses
equal but for case, so a duplicate needs stray spaces as well.


``POST /bulk-email/preview``
============================

Who a message would reach, now.  Nothing is sent and nothing is stored.  The
body is the message and its aim:

.. code-block:: json

   {"subject": "Spring safety seminar",
    "body": "Join us at Livermore on Saturday.\n\nBring your logbook.",
    "filters": {"kind": "friend", "county": "Marin,Napa"}}

``subject`` is required, at most 200 characters, one line, and free of control
characters, since the mail library refuses them in a header; ``body`` is
required plain text of at most 20,000 characters, a blank line separating
paragraphs.  Both are trimmed.  ``filters`` may be left out to aim at every
member and friend.  **200**:

.. code-block:: json

   {"count": 41,
    "skipped_count": 1,
    "recipients": [{"user_id": 12, "name": "Ann Able",
                    "email": "ann@example.org", "reason": ""}],
    "skipped": [{"user_id": 31, "name": "Gil Gone",
                 "email": "gil@example.org", "reason": "Account deactivated"}]}

``count`` and ``skipped_count`` are the lengths of the two lists, each in
surname order.  A refused message is **400** keyed by the field:

- ``subject``: *Write a subject.*, *A subject is one line.* (for any character
  ``str.splitlines`` breaks on, from a carriage return to U+2028), *A subject
  cannot carry control characters such as tabs.* (for any other character in
  Unicode's ``Cc`` category), or DRF's length message.
- ``body``: *Write the message.*, or DRF's length message.
- ``filters``: an object keyed by filter, carrying *Not a filter of the member
  list.* for a name the list does not have, or the list's own message for a
  value it refuses, such as ``{"filters": {"kind": ["Select a valid choice.
  donor is not one of the available choices."]}}``.


``GET /bulk-email/preview.csv``
===============================

The preview's list as a CSV download.  The query parameters are the filters,
checked as ``filters`` is above: a refusal is **400** under ``filters``.  The
file is ``caldart-bulk-email-preview-<YYYY-MM-DD>.csv``, dated the day it is
built, with the columns ``Name``, ``Email``, ``Result``, and ``Reason``:
everybody ``To send``, then everybody ``Skipped`` with the reason.


``POST /bulk-email/send``
=========================

Sends the message, with the same body as a preview and the same checks.  The list
is rebuilt at the moment of sending, so it is whoever the filters select then.
Each recipient is sent a copy of their own through ``caldart.mail.send_templated``,
from ``emails/bulk_email.{txt,html}``, logged in the email log under the purpose
``bulk_email`` (:doc:`email`).  Every copy goes over one connection from the
default mailer, opened once for the send; after a refusal it is closed, and the
next copy opens a fresh one.  The plain-text body is the message followed by
the house footer; the HTML body makes each paragraph a ``<p>``.  The subject is
sent as typed.

A copy the mail server refuses (an ``SMTPException`` or ``OSError``) is recorded
as ``failed`` with *Refused by the mail server*, and the rest still go.

The record is written before the first copy goes: the ``BulkEmail``, a
``pending`` row for every recipient, and a ``skipped`` row for every skip.  Each
copy's row and the send's counts are saved the moment it is tried, outside any
transaction, and ``sent_at`` is set when the last one has been.  The whole send
runs inside the request, which the worker and the proxy end after 60 seconds;
a send cut off there is *interrupted*: ``sent_at`` stays null, the counts say
how far it got, and the rows still ``pending`` name everyone never sent a copy.
The portal shows it as **Interrupted**.  :doc:`roadmap` describes moving the
send into a background job.  A send
whose filters select nobody who could be sent a copy is **400**
``{"filters": ["Nobody matches these filters."]}`` and stores nothing.

**201** with the stored send, as ``GET /bulk-email/{id}`` answers it.  The send
writes one ``bulk_email.send`` audit line naming the caller, the send, and its
``sent``, ``skipped``, and ``failed`` counts (:ref:`deploy-audit-log`).


``GET /bulk-email``
===================

Every send, the most recent first.  Unpaginated: a handful are sent a month.

.. code-block:: json

   [{"id": 7,
     "subject": "Spring safety seminar",
     "body": "Join us at Livermore on Saturday.\n\nBring your logbook.",
     "filters": {"kind": "friend"},
     "sender": "Grace Holloway",
     "created_at": "2026-10-02T10:00:00-07:00",
     "sent_at": "2026-10-02T10:00:04-07:00",
     "sent_count": 40,
     "failed_count": 1,
     "skipped_count": 1}]

``filters`` are the filters that carried a value.  ``sender`` is the sender's
display name, and blank once that account is deleted.  ``created_at`` is when
the send began and ``sent_at`` when every copy had been tried; ``sent_at`` is
null for an interrupted send, whose counts are as far as it got.


``GET /bulk-email/{id}``
========================

One send, as the history lists it, with ``recipients``: every person the filters
chose, in the order the send stored them (each copy sent or failed, in surname
order, then each skip):

.. code-block:: json

   {"id": 7,
    "recipients": [
      {"user_id": 12, "name": "Ann Able", "email": "ann@example.org",
       "status": "sent", "reason": ""},
      {"user_id": null, "name": "Bea Bell", "email": "bea@example.org",
       "status": "failed", "reason": "Refused by the mail server"}]}

``status`` is ``sent``, ``failed``, ``skipped``, or ``pending`` (a copy an
interrupted send never tried); ``reason`` is blank for a copy that went or was
never tried.  ``user_id`` is null once the account is deleted, while
``name`` and ``email`` stay as they were at send time.  **404** for an unknown
id.


``GET /bulk-email/{id}/recipients.csv``
=======================================

One send's results as a CSV download, ``caldart-bulk-email-<id>-recipients.csv``,
with the columns ``Name``, ``Email``, ``Result`` (``Sent``, ``Failed``,
``Skipped``, or ``Not sent``), and ``Reason``, in the order above.  **404** for an unknown id.
