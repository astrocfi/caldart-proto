=====
Email
=====

CalDART sends email, and reads one mailbox: the one undeliverable mail is
returned to.  This page covers how a message leaves the application, what a
production domain needs so that message is delivered, the backends development
and the tests use instead, what is recorded about every send, how bounces are
detected, and what happens to replies.


What the site sends
===================

Every message is rendered from a pair of templates in
``backend/templates/emails/``, one plain-text and one HTML, and sent by
``caldart.mail.send_templated``.  The template name is the message's
*purpose*, except for the notifications, which share the ``notification``
template and each carry the purpose ``notification_<slug>`` of their event.
``apps/mail/purposes.py`` gives each purpose the label the portal's email log
shows.  ``PURPOSE_LABELS`` holds the labels that never change.  A label that
depends on stored data comes from a source an app above mail registers with
``register_purpose_labels()`` from its ``AppConfig.ready()``;
``purpose_labels()`` merges the sources, in registration order, ahead of
``PURPOSE_LABELS``.  The reminders app registers the five reminder labels, worded
from the stored reminder schedule, so the mail app never imports it:

.. list-table::
   :header-rows: 1
   :widths: 30 34 36

   * - Purpose
     - Label
     - Sent by
   * - ``reminder_first``, ``reminder_second``, ``reminder_final``,
       ``reminder_expired``, ``reminder_lapsed``
     - Renewal reminder (60 days), (30 days), (7 days), (expired), (30 days
       after) on the default schedule; the days follow the stored reminder
       schedule (:ref:`reminders-schedule`)
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
   * - ``bulk_email``
     - Bulk email
     - the background bulk email sender, one copy per person in the batch, each
       built by ``apps.bulk_email.render`` and sent through the pass-through
       templates ``bulk_email_copy.{txt,html}`` (:doc:`bulk-email`)
   * - ``bulk_email_test``
     - Bulk email test
     - **Send me a test** on the compose screen: one copy of a bulk email to the
       sender alone, built as the background sender builds a copy, its subject
       starting ``[Test]`` (:ref:`bulk-email-test-copy`)
   * - ``notification_<slug>``, one per event, from ``notification_signed_up``
       to ``notification_callout_answer``
     - Notification: and the event's label, from Notification: Sign-up to
       Notification: Callout answer
     - the service that raised the event, once its transaction commits
       (:doc:`notifications`)

Every message comes from ``DEFAULT_FROM_EMAIL`` and carries a ``Message-ID``
generated on that address's domain, which its email log row records.  Only a bulk
email, and its test copy, sets a ``Reply-To`` header: the address its sender chose,
or ``BULK_EMAIL_REPLY_TO``, or the sender's own address
(:ref:`bulk-email-reply-to`).  ``From`` stays ``DEFAULT_FROM_EMAIL`` there too, so
SPF, DKIM, and DMARC still align.  Where any other template tells the reader how to
get in touch, it prints the contact address from the website's site settings, which
a website administrator edits in the Wagtail admin (:doc:`cms`).
``send_templated`` takes two keyword arguments for a sender that needs more:
``headers``, extra headers merged into the message (they cannot replace its
``Message-ID`` or ``From``), and ``reply_to``, the message's ``Reply-To`` address.


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
port 465; plain ``smtp://`` sends in the clear and is for a server on the
same machine only: Mailpit in development, or the machine's own postfix
(`A local postfix`_).  The
credentials are percent-encoded, so the ``@`` in a user name that is an email
address becomes ``%40``.  ``EMAIL_TIMEOUT`` (default 20 seconds) bounds each
conversation with the relay, so a relay that stops answering holds up one
request or one job step for that long and no longer.

Use a relay that is allowed to send for the domain in ``DEFAULT_FROM_EMAIL``:
the organization's own mail provider, or a transactional service such as
Amazon SES, Postmark, or Mailgun.  A home ISP's server, or a personal mailbox
signing in as itself, delivers to few inboxes.

.. _email-local-postfix:

A local postfix
---------------

A server that already runs a mail server, such as the machine that serves the
organization's website, can hand mail to its own postfix instead of a remote
relay.  The URL is plain SMTP to the loopback port, with no credentials:

.. code-block:: text

   smtp://localhost:25

``deploy/install.sh --email local`` writes exactly that as ``EMAIL_URL``
(:doc:`deployment`).  The installer installs no mail server, and when nothing
listens on port 25 it says so in a note, since mail fails until postfix is
installed and listening on localhost.  Postfix accepts mail from localhost for
any destination in its default configuration (``mynetworks`` holds the
loopback addresses), so nothing needs to authenticate.

Postfix then delivers the message itself, so the domain's records must name
this machine rather than a relay's:

* ``DEFAULT_FROM_EMAIL`` on a domain whose SPF record names this host (its
  ``a:`` or ``ip4:``/``ip6:`` entry), and DKIM signing set up in postfix
  (``opendkim``, for instance) if the domain's DMARC expects it; or
* postfix set up as a satellite system that forwards everything to the
  organization's relay, with ``relayhost = [smtp.example.org]:587`` and that
  relay's credentials in ``main.cf``, so the SPF and DKIM that already cover
  the relay cover this mail too.

Check the path end to end with Django's own command::

  sudo deploy/manage.sh sendtestemail you@example.org

and read ``journalctl -u postfix`` (or ``/var/log/mail.log``) for the
message's ``status=sent``, then its ``Authentication-Results`` as
`What the domain needs`_ describes.

The sender address
------------------

``DEFAULT_FROM_EMAIL`` is the ``From`` of every message and, as
``SERVER_EMAIL``, of the error mail Django sends to ``ADMIN_EMAILS``.  Pick an
address on the organization's own domain whose mailbox exists and that somebody
reads now and then; ``noreply@`` works as long as the mailbox behind it does (see
`Receiving`_).

The envelope sender (the ``MAIL FROM`` of the SMTP conversation, which the
receiving server records as ``Return-Path``) is where a server returns a message
it cannot deliver.  It is ``BOUNCE_ADDRESS`` when that is set, and
``DEFAULT_FROM_EMAIL``'s address otherwise.  ``send_templated`` passes the
envelope sender to Django as the message's ``from_email`` and
``DEFAULT_FROM_EMAIL`` as an explicit ``From`` header, which is how Django 6's
mailer lets the two differ; the reader sees ``DEFAULT_FROM_EMAIL`` either way, and
replies go there.  Put ``BOUNCE_ADDRESS`` on the same domain as
``DEFAULT_FROM_EMAIL``, so the SPF record that covers one covers both (see
`Bounces`_).

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

``manage.py check_mail_dns`` and the portal's **Mail delivery** screen look these
records up and say which are missing, malformed, or too weak, and whether the
mail host and ``BOUNCE_ADDRESS`` fit them (:ref:`deploy-mail-dns`).  Set
``DKIM_SELECTOR`` to the selector the DKIM record is published under so the check
can find it.

Check what the world sees with ``dig`` (``dnsutils`` on Debian and Ubuntu):

.. code-block:: console

   $ dig +short TXT caldart.example.org
   $ dig +short TXT relay1._domainkey.caldart.example.org
   $ dig +short TXT _dmarc.caldart.example.org

Then send a real message and read how it arrived.  Django's own
``sendtestemail`` command sends a one-line test through the configured mailer
(on a server, through ``deploy/manage.sh`` from :ref:`deploy-manage-commands`)::

  sudo deploy/manage.sh sendtestemail you@your-own-mailbox.example

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
error then travels on to the caller, which decides what the refusal means
(`When the mail server refuses`_).  The body itself is not stored.

A system administrator reads the log in the portal, on the **Sent Emails**
page, which filters by date, purpose, recipient, status, and attachments and
exports what it shows; the same rows come from
``GET /api/v1/system/emails`` (:doc:`api-system`) and, read-only, from the
Django admin.

**Sent** means the relay accepted the message.  It does not mean the message
reached an inbox.  A message the recipient's server later refuses for good turns
**Bounced** once the bounce check has read the report (`Bounces`_).  The Sent
Emails page filters on that status and shows when each message bounced and why.  A copy of a bulk email links from its row to that email's page on **Sent**
(``link`` in ``GET /system/emails``): the mail app knows nothing of bulk email, so
the bulk email app registers the link with ``apps.mail.links.register_log_links``.

.. _email-refused:

When the mail server refuses
----------------------------

A refusal is an ``smtplib.SMTPException``, for a message the server answers with
an error (credentials it will not accept, a sender or a recipient it will not
take), or an ``OSError``, for a server that cannot be reached at all (a connection
refused, a host that does not resolve, a TLS failure, a timeout), raised while
``send_templated`` hands the message over.  ``send_templated`` records the failed
row and raises ``caldart.mail.MailRefusedError`` from it.  That error's message is
the transport's class name and the SMTP reply code, such as
``SMTPRecipientsRefused (550)``, and never the transport's own text, which can
name an address.  It is an ``OSError``, so a job that catches the transport's
errors catches it unchanged, and ``caldart.mail.error_name`` gives a log line the
transport's class rather than ``MailRefusedError``.  An error rendering the
templates comes before the hand-over and is never a refusal: it is a bug and
fails loudly.  Every caller catches a refusal and carries on:

* Each scheduled job, and each send to many people (bulk email, notifications,
  rosters), catches the refusal for that one recipient, logs it to the journal,
  counts it among its failures, and carries on with the next.  The bulk email
  sender alone tries a temporary refusal again before it gives up
  (:ref:`bulk-email-pacing`).
* A payment's email (a receipt, a refund notice, a renewal notice) is caught and
  logged, and the payment stands.
* A request a person makes for themselves (a password reset, a registration,
  a fresh verification link, a change of address, a reactivation) answers
  exactly as it does when the message goes out.  So does a change an
  administrator saves that mails somebody along the way, such as the invitation
  a member added on the member record receives, since the change has committed.
  These sends go through ``caldart.mail.send_logging_refusal``, or
  ``caldart.mail.send_on_commit`` for a send queued for the commit.
* A send a user administrator asks for by name, the user record's **Send password
  reset** and **Resend verification message**, answers 503 with a sentence
  pointing at the Sent Emails page, so the administrator knows it did not go.

The request answers are listed endpoint by endpoint under
:ref:`refused sends <api-refused-send>`.  A refusal during one of those account
requests, or during a member record change that mails somebody, is logged at
ERROR on the ``caldart.mail`` logger by ``caldart.mail.log_refusal``, naming the
message and the account id, the transport's class, and the SMTP code, with no
traceback.  Production writes that logger to the journal and mails it to
``ADMIN_EMAILS`` (:doc:`configuration`), as it does an unhandled 500.  The other
senders above log a refusal on their own module's logger, to the journal only.  That error mail goes through the same mail server, so it is
often refused as well: the ``mail_admins`` handler
(``caldart.error_reports.QuietAdminEmailHandler``) then writes the failure to
standard error, which the journal keeps, instead of raising it into the request.
An unreachable server is waited on twice, once for the message and once for the
report, each bounded by ``EMAIL_TIMEOUT``.


.. _email-bounces:

Bounces
=======

A relay that accepts a message has not delivered it: the recipient's server can
still refuse it, a minute or a day later, and say so in a delivery-status report
(RFC 3464) mailed back to the envelope sender.  CalDART reads those reports from
a mailbox of their own and marks what they report.

How it works
------------

1. Every message ``send_templated`` sends carries a fresh ``Message-ID``, stored
   on its ``EmailLog`` row (``message_id``), and goes out with ``BOUNCE_ADDRESS``
   as its envelope sender.
2. ``manage.py check_bounces`` (``apps.mail.bounces.check_bounces``), run hourly by
   ``caldart-bounces.timer`` (:ref:`deploy-bounces`), signs in to the mailbox
   ``BOUNCE_IMAP_URL`` names over IMAPS with the standard library's ``imaplib``,
   verifying the server's certificate and host name
   (``ssl.create_default_context()``), and fetches every unseen message of at most
   1 MB without marking it.  A delivery report is a few kilobytes; a larger message,
   and one the server will not hand over, is *skipped*: logged, counted, and left
   unread.
3. Each message is read as a delivery-status report: a ``multipart/report`` with
   a ``message/delivery-status`` part.  Only a recipient block with ``Action:
   failed`` and a ``5.x.x`` ``Status`` counts.  A delay (``Action: delayed``), a
   transient ``4.x.x`` failure, a delivery notice, an auto-reply, and anything else
   that is not a report are *ignored*.
4. A permanent failure is matched to the row whose ``message_id`` is the
   original's ``Message-ID``, read from the report's ``text/rfc822-headers`` part
   or its returned ``message/rfc822`` copy.  A report that carries neither, or an
   id no row has, falls back to the latest row sent to the ``Final-Recipient``
   address (ignoring case) in the last seven days that the relay did not refuse.
   A failure neither finds is *unmatched*.  The fallback trusts the report: any
   message in the mailbox that is shaped as a delivery report and names an address
   CalDART mailed in the last seven days marks that send bounced and flags the
   address.  That is why the bounce mailbox must be one of its own, receiving
   nothing but the reports returned to ``BOUNCE_ADDRESS``: an address that anyone can
   write to is an address anyone can use to flag a member's email as bad.
5. A match turns the row's ``status`` to ``bounced`` with ``bounced_at`` and
   ``bounce_detail`` (the status code and the diagnostic text, cut to 255
   characters), and flags the account whose *current* address is the one the
   row was sent to: ``User.email_bounced_at`` and ``email_bounce_detail``.  An
   account that has moved to another address since is not flagged.  A row
   that is a copy of a bulk email (the purpose ``bulk_email``) is tied back to that
   copy as it is saved: the bulk email's recipient row with the same ``Message-ID``
   reads ``bounced`` with the same detail, and the bulk email's delivery report counts
   it as bounced (:ref:`api-bulk-email-delivery`).
6. Each message's writes are one database savepoint.  Header values have every
   control character, a NUL included, turned into a space before anything is
   stored, and a report whose writes the database still refuses is rolled back,
   logged by its message number alone, and counted as *ignored*, so one bad message
   cannot stop the run.
7. Each message read, ignored and unmatched ones included, is then marked seen, so
   the next run reads only what has arrived since.

A dry run (``--dry-run``, or the box on the Scheduled page) opens the mailbox
read-only (IMAP ``EXAMINE``), reads and matches exactly as a live one, and writes
nothing and marks nothing seen.  Every run prints, and ``POST /system/bounces/run``
answers, the counts ``bounced``, ``unmatched``, ``ignored`` and ``skipped`` with one
action per failure (:ref:`api-email-log`), and records a ``bounces.run`` audit
line.  A malformed ``BOUNCE_IMAP_URL``, or a mailbox that cannot be reached, signed
in to, opened, or read, stops the run with a sentence naming the host, never the
password: the command exits non-zero, so the unit shows ``failed``, and no audit
line is written, though rows a live run marked before the failure stay marked and
their messages stay seen.  With ``BOUNCE_IMAP_URL`` empty the run says bounce
checking is off and reads nothing.

``BOUNCE_IMAP_URL`` carries the mailbox password.  Error reports mailed to
``ADMIN_EMAILS`` mask the password in any URL a setting holds
(``DEFAULT_EXCEPTION_REPORTER_FILTER``, :doc:`configuration`), the parsed address
leaves the password out of its ``repr``, and the check's own frames are marked
sensitive, so a traceback shows none of their variables.

The flag on the account shows as a **Bounced** chip beside the address on the
member record and the user record, and Users and roles filters on it
(``?email_bounced=``).  It clears when the address changes, when a verification,
password reset, or invitation link sent to it is followed, and when a user
administrator presses **Clear bounce** on the user record
(:ref:`api-clear-bounce`).  Nothing stops mail going to a flagged address: the flag
tells an administrator the address needs correcting.

Setting up the mailbox
----------------------

1. Create a mailbox for bounces alone on the organization's mail provider, on the
   same domain as ``DEFAULT_FROM_EMAIL``: ``bounces@caldart.example.org``, say.
   Nothing else may be delivered there: the check marks every message it reads as
   read, and, through the recipient fallback above, any delivery report that
   reaches it can mark a recent send bounced.  Do not reuse a role address the
   public writes to, and turn off forwarding into it.
2. Make sure the provider offers IMAP over TLS (port 993) and, where it wants
   one, create an app password for the mailbox.
3. Set ``BOUNCE_ADDRESS`` to the mailbox's address and ``BOUNCE_IMAP_URL`` to it as
   an ``imaps://`` URL, with the user name and password percent-encoded:

   .. code-block:: text

      BOUNCE_ADDRESS=bounces@caldart.example.org
      BOUNCE_IMAP_URL=imaps://bounces%40caldart.example.org:app-password@imap.example.org/INBOX

   ``install.sh --bounce-address`` and ``--bounce-imap-url`` write both on a first
   install (:doc:`deployment`); on a running server, add them with ``sudoedit
   /etc/caldart/caldart.env`` and restart ``caldart-web``, since the web service
   sends the mail.
4. Rehearse a run: ``sudo deploy/manage.sh check_bounces --dry-run`` prints what
   the mailbox holds and what a live run would mark, and ``journalctl -u
   caldart-bounces`` shows the hourly runs.

Send a message to an address that cannot exist on a domain you control, such as
``no-such-person@caldart.example.org``, from a password reset or an invitation;
within the hour its row on the Sent Emails page reads **Bounced**.  A relay that
rewrites the envelope sender, as some transactional services do, returns the
reports to its own address instead: point ``BOUNCE_ADDRESS`` at an address the
relay forwards bounces to, or read the relay's own bounce list, since such a
report never reaches the mailbox.


.. _email-unsubscribe:

Unsubscribe links
=================

Bulk email comes in kinds, the email types a system administrator keeps
(:doc:`api-email-types`), and each person may turn off any type whose
``allow_opt_out`` is set.  Every copy of a bulk email of such a type carries a way
to do that without signing in; transactional mail (a receipt, a reminder, a
password link) carries none, because it is about the person's own account.

The token.
   ``apps/mail/unsubscribe.py`` signs the recipient's account id and the type's id
   with ``django.core.signing``, salt ``mail.unsubscribe``, timestamped.
   ``read_token`` refuses a token whose signature does not match, one older than
   ``UNSUBSCRIBE_TOKEN_MAX_AGE`` (180 days by default, :doc:`configuration`), one
   whose payload is not the shape it writes, and one naming an account or a type
   since deleted.  The link is ``<SITE_URL>/mail/unsubscribe/<token>``, built on
   ``SITE_URL`` so a site served under a path keeps it.

The headers.
   ``headers_for(user, email_type)`` answers, for a type that allows opting out,

   .. code-block:: text

      List-Unsubscribe: <https://caldart.example.org/mail/unsubscribe/<token>>, <mailto:contact@caldart.example.org?subject=unsubscribe>
      List-Unsubscribe-Post: List-Unsubscribe=One-Click

   which is what Gmail, Yahoo, and other mail programs read to show their own
   **Unsubscribe** button (RFC 2369 and RFC 8058).  A signed link is longer than a
   mail line, and the mail library's standard folding would write it as RFC 2047
   encoded words, which those programs do not read; ``caldart.mail`` writes every
   message with a header class that keeps ``List-Unsubscribe`` as itself, one URI to
   a folded line, whichever policy the mail backend uses.  The ``mailto:`` goes to the
   contact address in the site settings and is left out when there is none; the
   site reads no mailbox for it, so whoever reads the contact address acts on such a
   message by hand.  For a type that does not allow opting out the answer is empty.

The footer.
   ``footer_for(user, email_type)`` answers the line the copy's footer shows: for a
   type that allows opting out, *You receive <type> email from <organization>
   because you have not turned it off. To stop it, unsubscribe here:* followed by
   the same link; for one that does not, *<organization> sends <type> email to
   everyone it writes to, so it cannot be turned off.* with no link.

The page.
   ``GET /mail/unsubscribe/<token>`` renders a small page in the public site's shell
   naming the type, with one **Unsubscribe** button, and records nothing: a mail
   scanner that follows every link in a message must not unsubscribe anybody.  The
   button posts back to the same address, and so does a mail program's one-click
   unsubscribe; the ``POST`` records the opt-out with the source ``unsubscribe`` and
   answers **200** with *You will no longer receive <type> email from
   <organization>.*  The view is CSRF-exempt: a one-click ``POST`` arrives from the
   mail provider with no session and no token, and the signed address is the
   authorization.  A token that does not read is a **400** page saying the link has
   expired, and a type that no longer allows opting out records nothing and says
   so.  Every page links to the portal's Email preferences, where the person can
   turn the type back on after signing in.

An opt-out is audited as ``email.opt_out`` with the person as both actor and
target.  A recorded opt-out of a type that later stops allowing one stays in place,
unapplied, until the type allows it again.


Receiving
=========

The site runs no mail server and has no inbound address; the one mailbox it reads
is the bounce mailbox (`Bounces`_).  Two consequences follow, and each is worth
telling the organization before go-live.

Replies go to the sender address.
   A member who presses **Reply** writes to ``DEFAULT_FROM_EMAIL``.  Whatever
   the domain's mail provider does with that address is what happens to the
   reply; CalDART never sees it.  Point the address at a mailbox somebody
   reads, or make sure the contact address in the site settings is printed in
   the messages people reply to.

Bounces go to the envelope sender.
   With ``BOUNCE_ADDRESS`` set, the reports land in the bounce mailbox and the
   hourly check marks them.  Without it they land in the ``DEFAULT_FROM_EMAIL``
   mailbox, which CalDART does not read: the email log keeps saying **Sent**, and
   somebody who reads that mailbox corrects the address by hand, on the member's
   record or the user screen.  Most relays also list bounces and complaints in
   their own dashboards.

Sign-ups reach the organization as notifications.
   A person who joins as a member or a friend is sent a verification email, and a
   donor account made by a first gift is sent the gift's receipt.  The
   organization hears of a sign-up through the ``signed_up`` notification, sent
   to every address subscribed to it and to the roster contacts of the DART the
   person chose (:doc:`notifications`).

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
the server and the relay; with ``smtp://localhost:25`` it means postfix is not
running or not listening on localhost (``ss -ltn 'sport = :25'`` shows what
is).  ``journalctl -u caldart-web`` has the full message, and so does the error
mail to ``ADMIN_EMAILS`` when the server takes that one.

**The log says Sent, but the member saw nothing.**  Ask them to look in spam.
Then read the ``Authentication-Results`` of a test message as above: a
``fail`` on SPF, DKIM, or DMARC is the usual cause.  Finally look for a bounce
in the bounce mailbox (or, without ``BOUNCE_ADDRESS``, the ``DEFAULT_FROM_EMAIL``
mailbox) or the relay's dashboard.

**A bounce never shows up.**  Run ``sudo deploy/manage.sh check_bounces --dry-run``:
it says when ``BOUNCE_IMAP_URL`` is empty, names the host it could not reach or
sign in to, and counts what the mailbox holds.  A report counted as *unmatched*
carried no ``Message-ID`` CalDART sent and named an address CalDART has not
mailed in the last seven days: the send was older, or there was never a CalDART
send to that address at all (a report about some other mail, or one sent to the
mailbox by hand).  A report counted as *ignored* was a delay, a temporary failure,
not a delivery report at all, or one the database refused (the journal names its
message number).  A message counted as *skipped* is still unread in the mailbox:
the server would not hand it over, or it is larger than 1 MB.  Nothing counted means the
reports go elsewhere: check the ``Return-Path`` of a message in a mailbox you
control, which should be ``BOUNCE_ADDRESS``.
