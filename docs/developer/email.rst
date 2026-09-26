=====
Email
=====

CalDART sends email and receives none.  This page covers how a message leaves
the application, what a production domain needs so that message is
delivered, the backends development and the tests use instead, what is
recorded about every send, and what happens to replies and bounces.


What the site sends
===================

Every message is rendered from a pair of templates in
``backend/templates/emails/``, one plain-text and one HTML, and sent by
``caldart.mail.send_templated``.  The template name is the message's
*purpose*, and ``apps/mail/purposes.py`` gives each purpose the label the
portal's email log shows:

.. list-table::
   :header-rows: 1
   :widths: 30 34 36

   * - Purpose
     - Label
     - Sent by
   * - ``reminder_t60``, ``reminder_t30``, ``reminder_t7``,
       ``reminder_expired``, ``reminder_post30``
     - Renewal reminder (60 days), (30 days), (7 days), (expired), (30 days
       after)
     - the daily reminder scan (:doc:`reminders`)
   * - ``renewal_enabled``, ``renewal_notice``, ``renewal_card_expiring``,
       ``renewal_charged``, ``renewal_failed``, ``renewal_canceled``
     - Renewal turned on, Renewal notice, Card expiring, Renewal charged,
       Renewal declined, Renewal turned off
     - the portal, and the daily renewal run (:doc:`renewals`)
   * - ``receipt``, ``refund``
     - Receipt, Refund
     - a payment or refund, with the PDF attached (:doc:`api-payments`,
       :doc:`api-refunds`)
   * - ``contribution_statement``
     - Contribution statement
     - the yearly statement run, with the PDF attached (:doc:`statements`)
   * - ``member_invitation``, ``password_reset``, ``email_verification``
     - Invitation, Password reset, Email verification
     - the account flows (:doc:`api-auth`)
   * - ``scheduled_report``, ``dart_roster``
     - Scheduled report, DART roster
     - the daily report run (:doc:`scheduled-reports`)

Every message comes from ``DEFAULT_FROM_EMAIL``.  None sets a ``Reply-To``
header: where a template tells the reader how to get in touch, it prints the
contact address from the website's site settings, which a website
administrator edits in the Wagtail admin (:doc:`cms`).


Sending
=======

The connection
--------------

One variable, ``EMAIL_URL``, says where mail goes.  The settings translate it
into the single entry of Django's ``MAILERS`` setting, so the host, port, and
credentials are that mailer's options (:doc:`configuration`).  For a real
relay it is an SMTP URL:

.. code-block:: text

   smtp+tls://caldart%40example.org:app-password@smtp.example.org:587

``smtp+tls://`` starts TLS on the submission port, 587, which is what most
providers expect; ``smtp+ssl://`` speaks TLS from the first byte, usually on
port 465; plain ``smtp://`` sends in the clear and is for Mailpit only.  The
credentials are percent-encoded, so the ``@`` in a user name that is an email
address becomes ``%40``.  ``EMAIL_TIMEOUT`` (default 20 seconds) bounds each
conversation with the relay, so a relay that stops answering holds up one
request or one job step for that long and no longer.

Use a relay that is allowed to send for the domain in ``DEFAULT_FROM_EMAIL``:
the organization's own mail provider, or a transactional service such as
Amazon SES, Postmark, or Mailgun.  A home ISP's server, or a personal mailbox
signing in as itself, delivers to few inboxes.

The sender address
------------------

``DEFAULT_FROM_EMAIL`` is the ``From`` of every message and, as
``SERVER_EMAIL``, of the error mail Django sends to ``ADMIN_EMAILS``.  Its
address is also the envelope sender, so it is where a receiving server returns
a message it cannot deliver.  Pick an address on the organization's own domain
whose mailbox exists and that somebody reads now and then; ``noreply@`` works
as long as the mailbox behind it does (see `Receiving`_).

What the domain needs
---------------------

Receiving servers decide whether to trust a message by three DNS records on
the domain in the ``From`` address.  A domain without them lands in spam or is
refused outright by the large mailbox providers.

SPF
   A ``TXT`` record on the domain listing the servers allowed to send for it.
   The relay's documentation gives the ``include:`` to add; a domain has one
   SPF record, so add the relay to the existing one rather than publishing a
   second:

   .. code-block:: text

      caldart.example.org.  TXT  "v=spf1 include:_spf.relay.example ~all"

DKIM
   A public key the relay signs each message with, published as a ``TXT`` (or
   ``CNAME``) record under a selector the relay names:

   .. code-block:: text

      relay1._domainkey.caldart.example.org.  TXT  "v=DKIM1; k=rsa; p=MIIBIjANBg..."

DMARC
   A ``TXT`` record at ``_dmarc`` saying what a receiver should do with a
   message that fails both checks, and where to send reports.  Start with
   ``p=none`` and a report address, read the reports for a few weeks, then
   tighten it to ``quarantine``:

   .. code-block:: text

      _dmarc.caldart.example.org.  TXT  "v=DMARC1; p=none; rua=mailto:dmarc@caldart.example.org"

Check what the world sees with ``dig`` (``dnsutils`` on Debian and Ubuntu):

.. code-block:: console

   $ dig +short TXT caldart.example.org
   $ dig +short TXT relay1._domainkey.caldart.example.org
   $ dig +short TXT _dmarc.caldart.example.org

Then send a real message and read how it arrived.  Django's own
``sendtestemail`` command sends a one-line test through the configured mailer
(on a server, through ``caldart_manage`` from :ref:`deploy-manage-commands`)::

  caldart_manage sendtestemail you@your-own-mailbox.example

Open it in a mailbox you control, show the original message, and read the
``Authentication-Results`` header: it should say ``spf=pass``,
``dkim=pass``, and ``dmarc=pass``.  A test message goes straight to Django's
mailer, so it leaves no email log row.  The first real message the site sends,
a password reset to your own account for instance, is the check that the log
records it.


Backends
========

``EMAIL_URL``'s scheme picks the Django backend.  django-environ names five,
and ``caldart.settings.mailers`` knows the options each takes, so a scheme it
does not list stops start-up with ``ImproperlyConfigured``.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - ``EMAIL_URL``
     - What happens to a message
   * - ``smtp://``, ``smtp+tls://``, ``smtp+ssl://``
     - handed to the SMTP server in the URL.  Development points at Mailpit,
       production at the relay.
   * - ``filemail:////abs/path``
     - written as a file, one per connection, into the directory.  ``make
       e2e`` uses it (``frontend/e2e/.mail/``) so a spec can read the link a
       verification email carries.  Four slashes, because django-environ
       drops the first slash of the path.
   * - ``consolemail://``
     - printed to standard output, headers and both bodies.  Handy on a
       machine with no Mailpit.
   * - ``memorymail://``
     - kept in ``django.core.mail.outbox``.  The test settings select the
       in-memory backend themselves, whatever ``EMAIL_URL`` says, and the
       tests assert on that outbox.
   * - ``dummymail://``
     - discarded.

Whatever the backend, ``send_templated`` writes the email log row, so the log
shows a message the file or console backend caught exactly as it shows one
the relay accepted.


Mailpit
=======

``make up`` starts Mailpit beside Postgres, and ``.env.example`` points
``EMAIL_URL`` at it: an SMTP server on ``127.0.0.1:1025`` that accepts any
credentials, delivers nothing, and shows every message it caught in a web
inbox at http://localhost:8025/.  It keeps the newest 5000 messages and serves
every worktree on the machine, so deleting its messages deletes them for every
branch at once.

Beyond reading a message as its recipient would, the inbox shows the raw
source and headers, the attachments, and an HTML check of each message against
what the common mail clients support.  Its API answers scripted questions:

.. code-block:: console

   $ curl -s 'http://localhost:8025/api/v1/search?query=to:member@example.org'


What is recorded
================

Every message ``send_templated`` sends leaves one ``EmailLog`` row
(:doc:`data-model`): the address and the recipient's name at the time, the
account it concerned, the purpose, the subject, when it went, whether the
mail server took it, and the names of any attachments.  A server that refuses
the message is recorded as **failed** with the exception's class name, and the
error then travels on to the caller.  A request fails as it would without the
log, and each scheduled job catches the error for that one recipient, logs it
to the journal, counts it among its failures, and carries on with the next.
The body itself is not stored.

A system administrator reads the log in the portal, on the **System** page's
**Email log** panel, which filters by date, purpose, recipient, status, and
attachments and exports what it shows; the same rows come from
``GET /api/v1/system/emails`` (:doc:`api-system`) and, read-only, from the
Django admin.

**Sent** means the relay accepted the message.  It does not mean the message
reached an inbox.


Receiving
=========

The site receives no email.  It runs no mail server, has no inbound address,
and reads no mailbox.  Three consequences follow, and each is worth telling
the organization before go-live.

Replies go to the sender address.
   A member who presses **Reply** writes to ``DEFAULT_FROM_EMAIL``.  Whatever
   the domain's mail provider does with that address is what happens to the
   reply; CalDART never sees it.  Point the address at a mailbox somebody
   reads, or make sure the contact address in the site settings is printed in
   the messages people reply to.

Bounces are not detected.
   A message the relay accepted and the recipient's server later refused
   comes back as a bounce notice to the envelope sender, the
   ``DEFAULT_FROM_EMAIL`` mailbox.  CalDART does not read it, so the email log
   still says **Sent**, and the member's record carries no warning that the
   address is bad.  Somebody who reads that mailbox has to correct the address
   by hand, on the member's record or the user screen.  Most relays also list
   bounces and complaints in their own dashboards.  Detecting bounces is
   tracked as issue #266.

Nobody is told when someone signs up.
   A person who joins as a member or a friend is sent a verification email,
   and a donor account made by a first gift is sent the gift's receipt;
   nothing goes to the organization in either case.  The account
   administrator finds new sign-ups on the member list.  A
   notification to a configurable list of people and to the DART's roster
   leaders is tracked as issue #268.

Troubleshooting
===============

**Nothing arrives in development.**  Open http://localhost:8025/.  If Mailpit
is empty, check that ``EMAIL_URL`` in ``.env`` is ``smtp://localhost:1025``
and that ``docker compose ps`` shows the ``mailpit`` container up.

**The email log says Failed.**  The ``error`` column names the exception.
``SMTPAuthenticationError`` is a wrong user name or password in
``EMAIL_URL`` (many providers need an app password); ``SMTPSenderRefused``
is a ``DEFAULT_FROM_EMAIL`` the relay will not send as; ``TimeoutError`` or
``ConnectionRefusedError`` is the wrong host or port, or a firewall between
the server and the relay.  ``journalctl -u caldart-web`` has the full
message.

**The log says Sent, but the member saw nothing.**  Ask them to look in spam.
Then read the ``Authentication-Results`` of a test message as above: a
``fail`` on SPF, DKIM, or DMARC is the usual cause.  Finally look for a bounce
in the ``DEFAULT_FROM_EMAIL`` mailbox or the relay's dashboard.
