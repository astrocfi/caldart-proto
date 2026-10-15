=============================
API: authentication and users
=============================

The endpoints in ``apps.accounts`` — everything under ``/api/v1/auth/``, plus
``/api/v1/admin/users`` and ``/api/v1/roles``.  This page is the reference for
authentication and user administration; :doc:`api-reference` covers the
conventions every endpoint shares.


Conventions
===========

**Session authentication.**  The portal and the API are same-origin, so the
browser's session cookie is the credential; there is no token to store.
``caldart.authentication.CsrfEnforcingSessionAuthentication`` is the only
authentication class configured.

**CSRF.**  Every unsafe method needs an ``X-CSRFToken`` header, including the
anonymous ones on this page: register, login and its two-factor steps, logout,
the two password-reset endpoints, and the email-verify endpoint all refuse a POST
that carries no token.  Call
``GET /api/v1/auth/csrf`` whenever you have no ``csrftoken`` cookie to echo;
the SPA's ``api/client.ts`` does this automatically before every POST, PUT,
PATCH, or DELETE that finds the cookie missing.

**401, not 403, for anonymous callers.**  Session authentication has no
``WWW-Authenticate`` challenge, so DRF would normally answer 403.
``caldart.exceptions.caldart_exception_handler`` rewrites that to 401, which is
what the contract promises and what the SPA keys "sign in again" off.  A 403
therefore means one of two things: the caller is signed in and holds the wrong
role, or — when the ``detail`` starts ``CSRF Failed`` — the CSRF token is
missing or stale, which succeeds on a resend once a fresh token has been
fetched (see :ref:`api-csrf-bootstrap`).  The second reads the same whether or
not the caller has a session.

**Errors** are DRF-standard: ``{"detail": "..."}`` for view-level refusals, and
``{"<field>": ["..."]}`` for validation.  Password rules are reported against
the field they concern (``password``, ``new_password``) rather than in
``non_field_errors``, so a form can put the message under the right input.

**Pagination** is ``?page=&page_size=`` (25 by default, 200 maximum) with the
usual ``{count, next, previous, results}`` envelope.

.. _api-refused-send:

**When the mail server refuses.**  Several endpoints on this page send email
before they answer.  When the mail server refuses the message, or cannot be
reached, the attempt is recorded as a failed send in the email log
(:doc:`email`), and the refusal is logged on the ``caldart.mail`` logger, by the
transport's class and SMTP code with no traceback or address, which production
mails to ``ADMIN_EMAILS``
(:doc:`configuration`).  What the caller is told depends on who asked:

* A request people make for themselves answers exactly as it does when the
  message goes out: ``POST /auth/password/reset``, ``POST /auth/register``,
  ``POST /auth/password/change``, ``POST /auth/password/reset/confirm``,
  ``POST /auth/email/resend``, ``POST /auth/email/change``, ``POST /auth/email/verify``,
  ``POST /auth/email/undo``, and ``POST /auth/reactivate``.  A reset and a
  registration in particular must not tell the caller anything about the address,
  and any other answer would.
* A change an administrator saves that mails somebody along the way answers as
  it does when the message goes out too, because the change has committed: an
  reactivation, and the member record's create, edit, and reactivation
  (:doc:`api-members`).
* A send the user administrator asks for by name,
  ``POST /admin/users/{id}/send-password-reset`` or
  ``POST /admin/users/{id}/send-email-verification``, answers **503** and
  records nothing in the audit log, so the administrator knows the message did
  not go:

  .. code-block:: json

     {"detail": "The mail server did not accept the message. A system administrator can see the attempt on the Sent emails page."}

* ``POST /admin/users/{id}/require-new-password`` answers **503** too, but its
  change has committed by then and is recorded: the ``detail`` says the old password
  no longer works and every session is ended, and asks for the action to be pressed
  again, which mails a fresh link, once the server is fixed
  (:ref:`api-require-new-password`).

A refusal is ``caldart.mail.MailRefusedError``, which ``send_templated`` raises
only from an ``smtplib.SMTPException`` or an ``OSError`` (a connection refused, a
host that does not resolve, a TLS failure, a timeout) raised while the message is
handed to the mail server (:ref:`email-refused`).  Anything else, such as a
template that does not render, is a bug and answers 500.  The quiet answers go
through ``caldart.mail.send_logging_refusal``, or ``send_on_commit`` for a send
queued for the commit.

.. _api-after-response:

**Mail sent after the answer.**  ``POST /auth/password/reset`` and
``POST /auth/register`` must not take longer for an address that has an account than
for one that has none, so they render and send their message only once the answer
has gone: ``caldart.mail.send_after_response`` adds the send to the response's
closers, which Django runs when the WSGI server closes the response after writing it.
The send runs through ``send_logging_refusal``, so a refusal is logged as above; any
other error, a template that does not render included, has no answer left to turn
into a 500, so it is logged at ERROR on ``caldart.mail`` with its traceback.  The
test client closes every response it makes, so a test reads the outbox as usual.


The user payload
================

Every endpoint that returns an account returns the same object:

.. code-block:: json

   {
     "id": 12,
     "email": "marta.reyes@example.org",
     "pending_email": "",
     "first_name": "Marta",
     "last_name": "Reyes",
     "roles": ["member", "dart_leader"],
     "is_active": true,
     "membership": {
       "status": "current",
       "expires_on": "2027-06-30",
       "plan": "Annual",
       "is_lifetime": false
     },
     "profile_complete": true,
     "email_verified": true,
     "kind": "member",
     "friend_on": null,
     "admin_created": false,
     "can_use_aircraft": true
   }

``pending_email``
   The address a requested change of address waits to move the account to, or
   ``""`` when none is waiting (see `Changing the address`_).  ``email`` stays the
   address the account signs in with until the link mailed to ``pending_email`` is
   followed.  Read-only everywhere.

``roles``
   Slugs the account holds, always in privilege order (``member``,
   ``dart_leader``, ``user_admin``, ``account_admin``, ``website_admin``,
   ``system_admin``).  Roles are Django ``Group`` rows whose ``name`` is the
   slug, so adding a role later is a data change.

``membership``
   The membership summary from ``apps.members.services``.  ``status`` is one of
   ``current``, ``expired``, ``friend``, ``none``, and ``donor``; an effective
   friend's is ``friend``, with ``expires_on`` and ``plan`` null, except that a
   member who has never paid or been granted a term reads ``none`` (*Not yet
   paid*), with the same nulls (see :ref:`kinds of account <account-kinds>`).  ``expires_on`` is
   the end of the member's *unbroken* coverage, so an early renewal shows next
   year's date immediately, and it is ``null`` for a lifetime membership.
   A single-user endpoint such as ``/auth/me`` calls ``membership_status``,
   which works it out in Python; ``GET /admin/users`` reads it from the SQL
   annotations its queryset carries, so the page costs the same number of
   queries whatever its size (see :ref:`membership-status-sql`).  Both state
   the same rule and give the same answer.

``profile_complete``
   True when the member profile has ``phone``, ``address_line1``, ``city``,
   ``state``, ``postal_code``, and ``pilot_certificate_type`` filled in.  False when there is
   no profile at all.  The portal holds a reader whose profile is incomplete at the
   join wizard's profile step (see `How the portal uses this`_).

``email_verified``
   True once the account's owner has followed a link sent to the address the
   account holds now: a verification link (see `Email verification`_), the link
   that completed a change of address, or a password reset or invitation link.  A
   new account starts false.  While it is false the API refuses the session everything but a
   few endpoints (see `Unverified sessions`_), and the portal shows only the join
   wizard's verify step.

``kind``
   ``member``, ``friend``, or ``donor``, as stored (:ref:`kinds of account <account-kinds>`):
   what the person asked to be.  A member with a pending ``friend_on`` still
   reads ``member`` here until the day comes; ``membership.status`` already
   reads ``friend`` from that day.  A member who registered and has not paid
   reads ``kind: "member"`` with ``membership.status: "none"``, and the portal
   reads that to hold them at the join wizard's payment step, unless
   ``admin_created`` is true, when they reach the dashboard and are offered the
   dues there.

``friend_on``
   The date a member who asked to become a friend becomes one, or ``null``.
   Read-only on every endpoint here.

``admin_created``
   True for an account an account administrator created on New member
   (``POST /admin/members``, :doc:`api-members`).
   Such a person has joined already, as a member or a friend, so once
   ``email_verified`` is true the portal treats them as onboarded whatever
   ``profile_complete`` and ``membership`` say: their first sign-in after verifying
   opens the dashboard rather than the profile or pay step.  An unverified one is
   held at the verify step like anybody else, since the API refuses an unverified
   session (see `Unverified sessions`_).  False for an account made any other way.  Read-only everywhere.

``can_use_aircraft``
   True when the account may use the aircraft register and its own aircraft: a member
   whose membership is current, or a holder of a verifying role or ``system_admin``.
   False for a friend, a member who has not yet paid, and a member whose membership
   has expired; the portal hides My aircraft and its links then, and the server refuses
   the requests (:ref:`api-aircraft-access`).  Read-only everywhere.

The payload is read-only everywhere except ``PATCH /admin/users/{id}``, whose
answer also carries ``email_verified_at`` (below).


Authentication
==============

``GET /auth/csrf``
------------------

Issues a ``csrftoken`` cookie and answers with no body at all.  Open to
anyone; it is the one call a client makes before it can send an unsafe method.

Statuses: **204**, for anybody.

``POST /auth/register``
-----------------------

Registers an address for a member's or a friend's account, and answers the same way
whoever holds it, so the endpoint cannot be used to find out who has an account.
``email``, ``password``, ``first_name``, and ``last_name`` are required; ``kind``
is ``member`` (the default) or ``friend``.  Nobody is signed in.  Every address that
parses is answered **202** with this body, which echoes the address posted and
nothing else:

.. code-block:: json

   {"email": "marta.reyes@example.org", "password": "...",
    "first_name": "Marta", "last_name": "Reyes", "kind": "friend"}

.. code-block:: json

   {"detail": "We sent a message to marta.reyes@example.org. Follow the link in it to continue."}

What happens depends on who holds the address, and only the mailbox's owner learns
which, from the message mailed once the answer has gone
(:ref:`mail after the answer <api-after-response>`).  ``apps.members.services.register_member`` does the
work, and hashes the password first whichever case it is, so the time the request
takes does not tell the cases apart either.

**Nobody.**  In one transaction the endpoint creates the ``User`` of that kind with
the password, grants the ``member`` role and creates an empty ``MemberProfile``.  If
any part fails, none of it is written.  A member is an effective friend until a paid
or granted term starts, so the account reads ``membership.status: "friend"`` until
the first payment clears.  The address is mailed a verification link (see `Email
verification`_), and the account is unverified until it is followed; its owner signs
in with the password, from any browser, and the join wizard carries on.  No event is
raised yet: the join wizard asks for the DART at its profile step, and the
``PATCH /me/profile`` that completes the profile raises ``signed_up``
(:doc:`notification-events`).

**A donor.**  When the address belongs to a donor (:ref:`kinds of account
<account-kinds>`), no second account is made: the gifts on that account are not
shown to anyone who has not proved the address is theirs.  The posted ``password``
is not used: the donor's account keeps no usable password and gets a profile, and
the address is mailed a link, worded as a request to open a portal account, that
carries the names and the ``kind`` posted.  Following the link
(`POST /auth/email/verify`_) asks for a password and completes the upgrade: the
account takes that password, the names and the ``kind``, gains the ``member`` role,
and is verified.  The password is chosen by whoever follows the link, so only the
person who holds the mailbox can open the account.  Until then the account is still
a donor, and no login form or session signs it in.  The donations already on the
account stay on it, and the change of kind is audited as ``account.kind``.
Registering again with the address mails a fresh link.

**A member or a friend**, active or not.  Nothing about the account changes; the
posted password and names are not written.  The address is mailed *you already have
an account* (``apps.accounts.notices.send_account_exists_notice``,
``templates/emails/account_exists.{txt,html}``), worded for the account's state: an
active account is given the sign-in page with the address filled in and the
forgot-password page, and told that signing in offers a fresh verification link
while the address is unverified; a deactivated one is told that signing in and
pressing **Reactivate my account**, or choosing a new password, brings it back; one
a user administrator has closed (:ref:`api-reactivation-block`) is told to contact
the organization, and given no link.

Rejections, all 400, judged from the body alone, so they read the same whoever holds
the address:

``{"kind": [...]}``
   A kind other than ``member`` or ``friend``: nobody registers as a donor.

``{"password": [...]}``
   One of ``AUTH_PASSWORD_VALIDATORS`` refused it.  The validators run against
   the user-to-be, so a password that looks like the person's own name or email
   address is refused.

``{"<field>": ["<what to enter>"]}``
   A field was missing or blank.  All four of the account's fields are mandatory,
   and each says what to put there: *Enter your email address.*, *Choose a
   password.*, *Enter your first name.*, or *Enter your last name.*  An address
   that does not parse is *Enter an email address, such as name@example.org.*

Statuses: **202** for every address that parses; **400** for any rejection above;
**429** when the ``auth_register`` throttle is exhausted.  A refused message changes
nothing in the answer (:ref:`refused sends <api-refused-send>`).

``POST /auth/login``
--------------------

Starts a session and returns the user payload.  Email matching is
case-insensitive (``UserManager.get_by_natural_key`` uses ``email__iexact``).  An
account that needs a second factor is not signed in yet: the answer is
``{"mfa": "verify"}`` or ``{"mfa": "enroll"}``, and the code step finishes the
sign-in (:ref:`api-two-factor`).

.. code-block:: json

   {"email": "marta.reyes@example.org", "password": "..."}

.. code-block:: json

   {"id": 12, "email": "marta.reyes@example.org", "first_name": "Marta",
    "last_name": "Reyes", "roles": ["member", "dart_leader"], "is_active": true,
    "membership": {"status": "current", "expires_on": "2027-06-30",
                   "plan": "Annual", "is_lifetime": false},
    "profile_complete": true, "email_verified": true}

* **400** ``{"detail": "Incorrect email address or password."}`` — wrong
  credentials.  The message never says which half was wrong, and an address
  that belongs to a deactivated account is answered with exactly this body
  whenever the password does not match, so a guess cannot be used to find out
  which addresses are registered.
* **403** ``{"detail": "This account is deactivated. You can reactivate it.",
  "code": "deactivated"}`` — the password matched, but ``is_active`` is false.
  Only somebody who already holds the password sees this.  The ``code`` tells the
  portal to offer reactivation, which posts the same credentials to
  ``POST /auth/reactivate`` (:ref:`api-deactivation`).
* **403** ``{"detail": "This account has been closed. Contact CalDART to reopen
  it."}`` — the password matched, but a user administrator has blocked the
  account from reactivating (:ref:`api-reactivation-block`).  It carries no
  ``code``, so the portal shows the sentence and offers no reactivation; the
  organization's name comes from the site settings.

A donor cannot sign in at all.  A donor's account holds no usable password, and
even one that somehow does is answered with the same 400 as wrong credentials.
The refusal is made by the authentication backend
(``apps.accounts.backends.AccountBackend``), so it holds for every way into a
session, and a session that names a donor reads as signed out.

An account whose address is unverified signs in like any other and gets its
session, but that session reaches only the endpoints listed under `Unverified
sessions`_ until the address is verified.

Every wrong password counts against the address (:ref:`api-login-lockout`),
and a locked-out address is refused with **429** whatever the password, before it
is checked.

Statuses: **200** with the user payload and a session cookie, or with
``{"mfa": ...}`` and a session holding the pending sign-in; **400** for a missing
field or wrong credentials; **403** for a deactivated or closed account whose
password was correct; **429** when the ``auth_login`` throttle is exhausted or the
address is locked out.

``POST /auth/logout``
---------------------

Ends the session and answers with no body.  Safe to call when nobody is signed
in: the answer is the same either way, so a client can sign out without first
working out whether it is signed in.

Statuses: **204**, for anybody.

``GET /auth/me``
----------------

The signed-in user's payload.  This is the portal's single source of truth for
identity; the SPA caches it under the TanStack Query key ``['auth', 'me']`` and
everything that can change who you are writes or invalidates that key.  The
body is the user payload above, unchanged.

Statuses: **200**; **401** when anonymous.


.. _api-two-factor:

Two-factor sign-in
==================

An account signs in with a second factor -- a six-digit code from an
authenticator app, or one of its backup codes -- when it **needs** one:

* a role it holds requires it: ``user_admin``, ``treasurer``, ``account_admin``,
  ``management``, ``website_admin``, or ``system_admin``
  (``apps.accounts.roles.MFA_REQUIRED_ROLES``), read as effective roles, so a
  Django superuser is required too;
* or its owner turned two-factor sign-in on (a confirmed ``TotpDevice``, see
  :doc:`data-model`).

No role requires it of a demo account (``User.is_demo``, the accounts
``seed_demo`` writes) while ``DEMO_ACCOUNTS_SKIP_TWO_FACTOR`` is on, which it is
in development and off in production unless the server's environment turns it on
(:ref:`configuration-demo-two-factor`).  Such an account signs in with its
password alone, keeps a session that never passed a second factor, reads
``required_by_role`` as false, and may turn two-factor sign-in off.  A demo
account with a confirmed device is still asked for a code.  ``create_admin``
taking an account back clears the mark, and so do a new password, changed
(`POST /auth/password/change`_) or set from a reset link
(`POST /auth/password/reset/confirm`_), and a completed change of the account's
address.  Once the mark is gone, a role that requires two-factor sign-in requires
it again: a session that never passed a second factor is signed out at its next
request, and the next sign-in asks the account to set one up.

The code is RFC 6238: HMAC-SHA-1, six digits, 30-second steps, with one step of
drift either way accepted.  The device remembers the step of the last code it
accepted (``last_used_step``), and a code from that step or an earlier one is
refused, so a code is never accepted twice.  The issuer an authenticator app
shows is the organization's name from the site settings, and the account name is
the email address.  The services live in ``apps.accounts.mfa``.

**Backup codes.**  Turning two-factor sign-in on makes ten backup codes, each two
groups of five characters from a 31-character alphabet without look-alikes
(``abcde-fghjk``), drawn with ``secrets``.  They are shown once.  A backup code is
accepted wherever a code is asked for, in any case, with or without its hyphen and
spaces, and each works **once**.  Only a keyed hash is stored (``RecoveryCode``,
:doc:`data-model`).  Making a new set replaces every code of the old one.

**Nothing secret is logged.**  The secret, a code, and a backup code reach
neither the application log nor the audit log.

The sign-in
-----------

A right password for an account that needs a second factor does **not** start a
session.  ``POST /auth/login`` (and ``POST /auth/reactivate`` -- every endpoint that
signs somebody in goes through ``apps.accounts.api.sign_in.start_session``; a
registration signs nobody in) stores
a *pending sign-in* in the caller's session and answers **200** with what is still
owed, and nothing about the account:

.. code-block:: json

   {"mfa": "verify"}

``verify`` asks for a code; ``enroll`` means the account must use a second factor
and has no device yet, so it sets one up first.  The pending sign-in holds the
account's id, a fingerprint of its password (the session auth hash), when it
started, how many wrong codes it has taken, and whether its owner has been warned
of one.  It is refused, and cleared, five minutes after the password step, after the
fifth wrong code, once the password has changed, and once the account can no longer
sign in (a donor, blocked from reactivating, or deactivated).  It lives in the
session of the browser that gave the password, so a code posted from anywhere else
finishes nothing.  Storing it changes the session's key first
(``cycle_key``), so a key somebody planted in the browser before the password was
typed never carries the pending sign-in: whoever holds the old key can neither give
the code nor enroll a device on it.  Signing in at the end changes the key again.

``POST /auth/reactivate`` for an account that needs a second factor reactivates
nothing yet: the account stays deactivated, and its pending sign-in is marked
``reactivate``, the one case in which a pending sign-in may name a deactivated
account.  The code step then reactivates it (as ``/auth/reactivate`` does for any
other account) and signs it in, in one transaction; a block set in between refuses
it with the closed sentence and a **403**.  A password alone therefore never brings a
staff account back.

The code steps act on the pending sign-in and on nothing else:

``POST /auth/login/mfa``
   ``{"otp": "123456"}`` -- an authenticator code or a backup code.  A right code
   calls ``django.contrib.auth.login``, which gives the session a new key, marks
   the session as having passed the second factor, clears the pending sign-in and
   the address's short count of failed attempts, and answers the user payload a
   sign-in gives.

``POST /auth/login/mfa/enroll``
   No body.  For a pending sign-in that must enroll: draws a fresh secret, keeps it
   in this session (``_caldart_mfa_enrollment``, with the account's id, for ten
   minutes) without writing anything to the database, and answers what the app
   needs:

   .. code-block:: json

      {"secret": "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
       "otpauth_uri": "otpauth://totp/CalDART:marta.reyes%40example.org?secret=...&issuer=CalDART",
       "qr_svg": "<svg ...>...</svg>"}

   ``qr_svg`` is the QR code of ``otpauth_uri``, drawn on the server by ``segno``
   as an SVG document; ``secret`` is for typing in by hand.  Calling again replaces
   the secret this session holds and no other: each browser confirms only the secret
   it was shown, so a second sign-in at this step cannot spoil the first one's.  An
   account that already has a confirmed device is never offered this: a password
   alone cannot replace a working device.

``POST /auth/login/mfa/enroll/confirm``
   ``{"otp": "123456"}`` -- the first code from the new device.  A right code
   stores the device, confirmed, with the session's secret (the account's row is
   locked, so of two browsers confirming at once the second finds two-factor sign-in
   on), makes ten backup codes, signs in and marks the session as
   ``/auth/login/mfa`` does, and answers the user payload and the codes, the only
   time they are shown:

   .. code-block:: json

      {"user": {"id": 12, "email": "marta.reyes@example.org", "...": "..."},
       "recovery_codes": ["abcde-fghjk", "mnpqr-stuvw", "..."]}

Each code step answers:

* **400** ``{"otp": ["That code is not right. Enter the current code from your
  app, or a backup code."]}`` for a wrong code, which counts against the pending
  sign-in and against the address's lockout, both its fifteen-minute count and its
  day's count of wrong codes; the first wrong code of a pending sign-in mails the
  account (``mfa_wrong_code``), since only somebody who knows the password gets
  that far.  ``{"otp": ["Enter the code from your authenticator app, or a backup
  code."]}`` answers an empty one;
* **400** ``{"detail": "Your sign-in has expired. Enter your email address and
  password again.", "code": "mfa_expired"}`` when there is no pending sign-in to
  finish -- none was started, it expired, it took its fifth wrong code (that code
  is answered so), the password changed, or it is at the other step;
* **429** when the address is locked out (:ref:`api-login-lockout`), which also
  clears the pending sign-in, or when the ``auth_mfa`` throttle is exhausted.

All three are open to anonymous callers, need the CSRF token like every unsafe
method, and are on the unverified session's list (`Unverified sessions`_).

The session mark
----------------

A session that passed the second factor carries a mark under the session key
``_caldart_mfa_verified``: the account's id and the time, written by
``apps.accounts.mfa.mark_session`` after ``login``.  ``login`` keeps the data of
the session it rotates, and ``update_session_auth_hash`` after a password change
keeps it too, so the mark survives both.  Sessions are stored on the server
(Django's database session engine), so no client can write it, and it names the
account, so it never vouches for another.  Turning two-factor sign-in on while
signed in marks the session as well, and turning it off takes the mark away
(``apps.accounts.mfa.unmark_session``), so a role that requires it later asks that
session for it again.

``apps.accounts.middleware.MfaSessionMiddleware``, installed right after
``AuthenticationMiddleware``, signs out (``django.contrib.auth.logout``) every
session of an account that needs a second factor and carries no mark for it,
before the view runs, and the request carries on anonymous.  That covers a session
from before two-factor sign-in, a session whose account was given a required role
after it signed in, a session whose account's owner turned two-factor sign-in on
elsewhere, and a session of the Wagtail or Django admin.  An anonymous request --
a pending sign-in included -- passes untouched, as do ``POST /auth/logout`` and
every path outside Django's sessions; static files are served by WhiteNoise before
any session is read.

The admin sites
---------------

The Wagtail admin, the Django admin, and the public site's private pages share
the portal's session and serve no login form of their own, so there is one way to
sign in.  ``/admin/login/``, ``/django-admin/login/``, and Wagtail's
``/_util/login/`` (``caldart.views.admin_login_redirect``) redirect to the portal's
sign-in, ``LOGIN_URL``, carrying ``?next=`` only when it is a path on this site --
it starts with one ``/`` and passes ``url_has_allowed_host_and_scheme`` for the
request's host -- and dropping it otherwise.  ``WAGTAILADMIN_LOGIN_URL`` and
``WAGTAIL_FRONTEND_LOGIN_URL`` are ``LOGIN_URL`` too, so Wagtail sends a reader its
admin or a private page refuses straight there, with the page as ``next``.  Every
password is changed in the portal as well: ``/django-admin/password_change/``
(``caldart.views.portal_password_change``) redirects to the portal's Change
password, and the Django admin sets no other account's password.

Everything that sends a reader to the sign-in names ``next`` as a full site path:
the portal's guard and links a route under the portal's base (``/portal/admin/users``),
and Django a page of the guide, an admin site, or the public site (a members-only
page).  So the sign-in page (``nextTarget`` in ``LoginPage.tsx``) keeps a path under
the portal's base in the SPA and opens any other as a full-page navigation once the
person has signed in.  A reader who arrives already signed in goes straight on, except
with an admin page as ``next`` -- the admin sent them because their account cannot
open it -- when they are taken to the portal's dashboard.

Your own two-factor sign-in
---------------------------

These need a session; an anonymous caller gets **401**.

``GET /auth/mfa``
   .. code-block:: json

      {"enabled": true, "required_by_role": false, "recovery_codes_remaining": 9}

   ``enabled`` is true with a confirmed device; ``required_by_role`` is true when
   a role the account holds requires two-factor sign-in, which then cannot be
   turned off; it is false for a demo account while
   ``DEMO_ACCOUNTS_SKIP_TWO_FACTOR`` is on.

``POST /auth/mfa/enroll``
   ``{"current_password": "..."}``, so a session left open on somebody else's
   screen cannot attach a stranger's phone.  Answers the same ``{"secret",
   "otpauth_uri", "qr_svg"}`` as the sign-in's enroll step, the secret kept in this
   session the same way.  **400** ``{"current_password": ["That is not your current
   password."]}``; **400** ``{"detail": "Two-factor sign-in is already on for this
   account."}`` when it is.

``POST /auth/mfa/enroll/confirm``
   ``{"otp": "123456"}``.  Confirms the device, marks the session, and answers
   ``{"recovery_codes": [...]}``.  **400** under ``otp`` for a wrong code;
   **400** ``{"detail": "Start setting up two-factor sign-in first."}`` before
   ``/enroll`` in this session, and the *already on* sentence after confirming.

``POST /auth/mfa/recovery-codes``
   ``{"otp": "123456"}`` -- an authenticator code, or one of the backup codes
   being replaced.  Replaces every backup code and answers ``{"recovery_codes":
   [...]}``.  **400** under ``otp`` for a wrong code; **400** ``{"detail":
   "Two-factor sign-in is not on for this account."}`` without a device.

``POST /auth/mfa/disable``
   ``{"current_password": "...", "otp": "123456"}``.  Deletes the device and every
   backup code, and answers **204**.  A role that requires two-factor sign-in is
   refused before the body is read::

      403 {"detail": "Your role requires two-factor sign-in, so it cannot be turned off. If you have lost your phone, ask a user administrator to reset it."}

   and recorded at WARNING as ``action=account.mfa_disable ... reason=mfa_required``.
   **400** ``{"current_password": ["That is not your current password."]}``,
   **400** under ``otp`` for a wrong code, and **400** ``{"detail": "Two-factor
   sign-in is not on for this account."}`` without a device.

A wrong code at any of these counts against the address's lockout, and a
locked-out address is answered **429**.  Every ``POST`` here is throttled under
``auth_mfa``.

The administrator's reset is ``POST /admin/users/{id}/reset-two-factor``
(:ref:`api-reset-two-factor`).

What is mailed and recorded
---------------------------

The account is mailed a short notice once each change commits
(``templates/emails/mfa_*.{txt,html}``, :doc:`email`): two-factor sign-in turned
on (``mfa_enabled``) or off (``mfa_disabled``), reset by an administrator
(``mfa_reset``), a backup code used, with how many remain
(``mfa_recovery_code_used``), new backup codes made
(``mfa_recovery_codes_regenerated``), a wrong code after a right password
(``mfa_wrong_code``, once per pending sign-in), and a lockout (``sign_in_locked``,
once per window).  A refused send leaves the change standing
(:ref:`refused sends <api-refused-send>`).  The audit log records
``account.mfa_enable``, ``account.mfa_disable``, ``account.mfa_recovery_used``,
``account.mfa_recovery_codes``, and ``account.mfa_reset``, ids only.


Passwords
=========

``POST /auth/password/change``
------------------------------

Replaces the signed-in account's own password and answers with no body.
Requires a session.

.. code-block:: json

   {"current_password": "...", "new_password": "..."}

The view calls ``update_session_auth_hash`` afterwards, so changing your
password does not sign you out of the browser you changed it from.  Other
sessions are invalidated, because the session auth hash is derived from the
password.  A new password clears a demo account's mark (:ref:`api-two-factor`),
so a demo account a role requires two-factor sign-in of, signed in without one, is
signed out at its next request instead, and its next sign-in asks it to set up an
authenticator app.

The new password is written only while the stored one is still the one the
request checked ``current_password`` against.  When something else replaced it
in the meantime (another change, a reset, or ``create_admin`` clearing it), the
change writes nothing, leaves the session alone, and answers **401** with
``{"detail": "This account's password was changed elsewhere. Sign in again."}``.

The change is audited as ``action=account.password_change actor=12 target=12
reset=false``, and the account's address is mailed *your password was changed*
(``apps.accounts.notices.send_password_changed_notice``,
``templates/emails/password_changed.{txt,html}``): when it happened, and the
forgot-password page for an owner who did not make the change.  A mail server that
refuses it leaves the answer unchanged (:ref:`refused sends <api-refused-send>`).

* ``{"current_password": [...]}`` — did not match, or *Enter your current
  password.* when it was left empty.
* ``{"new_password": [...]}`` — refused by a password validator, or *Choose a new
  password.* when it was left empty.

Statuses: **204**; **400** for either rejection above or a missing field;
**401** when anonymous, or when the stored password changed during the request.

``POST /auth/password/reset``
-----------------------------

Mails a reset link to the address, and answers with no body **whatever
happens**.  Whether the address is registered or has never been seen, the
answer is identical: the endpoint must not be usable to enumerate members.  A malformed address is still a 400, since that
is a client bug rather than an answer about the database.

.. code-block:: json

   {"email": "marta.reyes@example.org"}

A donor is mailed nothing, since a donor cannot sign in, and neither is an
account a user administrator has blocked from reactivating
(:ref:`api-reactivation-block`).  When there is an account of any other kind,
active or deactivated,
``apps.accounts.services.send_password_reset_email`` renders ``templates/emails/password_reset.{txt,html}`` and mails a link::

    {SITE_URL}/portal/reset-password?uid=<urlsafe_base64(pk)>&token=<token>

The token comes from ``django.contrib.auth.tokens.default_token_generator``, so
it is invalidated by the password changing or by ``PASSWORD_RESET_TIMEOUT``
(three days by default) elapsing.  In development Mailpit catches the mail on
SMTP 1025; read it at http://localhost:8025/.

The address is looked up before the answer, the same one query whether or not it
matches, and the message is rendered and sent after the answer has gone
(:ref:`mail after the answer <api-after-response>`), so the time the request takes does not say whether
there was anybody to mail.

``apps.accounts.services.build_reset_url`` builds that link, stripping any
trailing slash from ``SITE_URL``, and the invitation an administrator-created
account receives (:doc:`api-members`) uses the same function, so both links are
spent at the confirm endpoint below.

Statuses: **204**, registered address or not, and whether or not the mail
server took the message (:ref:`refused sends <api-refused-send>`); **400** for a
missing or malformed address; **429** when the ``auth_password_reset`` throttle
is exhausted.

``POST /auth/password/reset/confirm``
-------------------------------------

Spends a reset link: sets the password it authorizes, and answers with no
body.

.. code-block:: json

   {"uid": "MTI", "token": "cs2k3t-4f2a...", "new_password": "..."}

Every way a link can be unusable — a mangled ``uid``, an unknown user, a
donor's account, a token that has expired or has already been spent — returns the same ``{"token": ["That password reset link is invalid or has
expired. Request a new one."]}``.  So does a link whose account's password
changed between the check and the write (another reset, or ``create_admin``
clearing it): the new password is written only while the stored one is still
the one the link was signed over.  A weak new password is reported separately
under ``new_password``.

The endpoint does not sign the user in; the portal sends them to ``/login``.
The link could only have reached the owner of the address, so spending it also
marks an unverified address verified (``email_verified_at`` is set to now, and
an ``account.email_verified`` audit line is written); an address already
verified keeps its original time.  Either way, any bounce recorded against the
address is cleared, and so is a demo account's mark (:ref:`api-two-factor`).

A link for a deactivated account is accepted, and spending it reactivates the
account exactly as ``POST /auth/reactivate`` does — the person proved the address
and chose to come back — except that nobody is signed in: the portal sends them
to ``/login`` as for any reset.  A good link for an account a user administrator
has blocked from reactivating (one mailed before the block) is refused with
``{"token": ["This account has been closed. Contact CalDART to reopen it."]}``,
the organization's name read from the site settings, and no password is set.  The block is
read again from the locked account row, so one set while the reset is under way
refuses it the same way and rolls the whole reset back.

A reset that replaces a password the account already had is audited as
``account.password_change`` with ``reset=true``, and the address is mailed the same
*your password was changed* notice as ``POST /auth/password/change``, once the reset
commits.  Setting the first password of an account that had none, from an
invitation or after an undone change of address (`POST /auth/email/undo`_), is
neither audited nor reported.

Statuses: **204**; **400** for an unusable link, a closed account, a weak
password or a missing field; **429** when the ``auth_password_reset`` throttle is exhausted, which
is the same budget the request endpoint draws on.


.. _api-deactivation:

Deactivating and reactivating your own account
==============================================

A member or a friend can switch their own account off and back on with these two
endpoints.  An administrator does the same for somebody else with the account
status actions (:ref:`api-account-status` below, and the member record's actions
in :doc:`api-members`), which do everything these do; ``is_active`` is never part
of an edit.  The functions that write the flag live in ``accounts.status``.

While an account is deactivated, every membership term it held with time left is
``suspended`` (see :doc:`data-model`).  A suspended term never covers a day and
never counts as a past term, so an account whose only terms are suspended reads
as ``friend``; the reminder scan leaves suspended terms out altogether.

``POST /auth/deactivate``
-------------------------

Deactivates the signed-in account and ends its session, answering with no body.

.. code-block:: json

   {"current_password": "..."}

In one transaction, holding a lock on the account's row so that a second,
concurrent request waits and then finds the account already inactive and does
nothing:

#. a system administrator or a donor is refused (below), which changes nothing;
   otherwise ``is_active`` is cleared (and any change of address still waiting
   dropped), ``account.deactivate`` is recorded with
   ``self_service=true``, and the ``account_deactivated`` event is raised with no
   actor (``accounts.status.deactivate_own_account``);
#. every active or paused renewal mandate — automatic renewal or recurring
   donation — is canceled by ``payments.renewals.mandates.cancel_mandate`` with the
   account as its own actor (a self-service ``renewal.cancel``, the
   ``auto_renewal_off`` event with ``how="deactivated"``, and the usual "automatic
   renewal is off" email once the transaction commits), and a pending one is discarded
   (``payments.renewals.mandates.cancel_all_mandates``);
#. every active term that is lifetime or ends on or after today — the covering
   term and any renewal already paid for that starts later — is set to
   ``suspended``, each recorded as ``membership.correct`` with
   ``status=suspended`` (``members.services.suspend_terms``).

The session is then logged out.  The kind, the roles, the profile and every
payment are kept.

A checkout already in progress is left alone.  If its payment is confirmed after
the account is deactivated, the term it buys is created ``suspended``
(``members.services.activate_term``), exactly as if it had been suspended by the
deactivation itself: the account does not read as ``current`` while nobody can
sign in to it, and reactivating restores the term the same way.

* **400** ``{"current_password": ["That is not your current password."]}``.
* **400** ``{"detail": "A system administrator cannot deactivate their own
  account."}`` — the ``system_admin`` role or a Django superuser.  Recorded at
  WARNING as ``action=account.deactivate ... reason=system_admin_target``.
* A donor cannot sign in and no session names one, so a donor reaches this endpoint
  only as an anonymous caller, answered 401.  The service behind it still refuses a
  donor, with "A donor has no portal account to deactivate." recorded with
  ``reason=donor_account``, as a guard rather than a path anybody takes.

Statuses: **204**; **400** for any refusal above, which changes nothing;
**401** when anonymous.

``POST /auth/reactivate``
-------------------------

Brings a deactivated account back and signs it in, answering with the user
payload.  It takes the same body as a sign-in, and shares its throttle scope,
``auth_login``.

.. code-block:: json

   {"email": "marta.reyes@example.org", "password": "..."}

Only an inactive account that is not a donor's, whose password matches, is
reactivated (``accounts.status.deactivated_account``; the address is compared
case-insensitively).  The account's row is locked for the transaction, so of two
concurrent requests the second finds the account active and is refused.  Then:

#. ``is_active`` is set, ``account.activate`` is recorded with
   ``self_service=true``, and the ``account_reactivated`` event is raised with no
   actor; the kind and the roles are exactly as they were;
#. each suspended term becomes ``active`` when it is lifetime or ends on or after
   today, so the membership resumes through its original date, and ``expired``
   when its end passed in the meantime, each recorded as ``membership.correct``
   (``members.services.restore_terms``);
#. an account whose address was never verified is mailed a verification link
   once the transaction commits.

Canceled mandates stay canceled.  This works for an account an administrator
deactivated as well as one its owner deactivated.  The answer is what a sign-in
gives: ``{"mfa": ...}`` for an account that needs a second factor
(:ref:`api-two-factor`), and otherwise the user payload with ``is_active`` true:

.. code-block:: json

   {"id": 12, "email": "marta.reyes@example.org", "first_name": "Marta",
    "last_name": "Reyes", "roles": ["member"], "is_active": true,
    "membership": {"status": "current", "expires_on": "2027-06-30",
                   "plan": "Annual", "is_lifetime": false},
    "profile_complete": true, "email_verified": true, "kind": "member",
    "friend_on": null}

An administrator's reactivation — ``POST /admin/users/{id}/reactivate`` or
``POST /admin/members/{user_id}/reactivate`` — brings the suspended terms back the
same way, each ``membership.correct`` recorded under the administrator.

* **400** ``{"detail": "Incorrect email address or password."}`` — a wrong
  password, an active account, an unknown address, or a donor, all answered
  with the body a failed sign-in gives, and counted against the address as a
  failed sign-in is (:ref:`api-login-lockout`).
* **403** ``{"detail": "This account has been closed. Contact CalDART to reopen
  it."}`` — the password matched, but a user administrator has blocked the
  account from reactivating (:ref:`api-reactivation-block`); it stays
  deactivated, and ``accounts.status.reactivate_own_account`` refuses it the same
  way, recorded as ``action=account.activate ... reason=reactivation_blocked``.

Statuses: **200** with the user payload and a session cookie, also when the mail
server refuses the verification link (:ref:`refused sends <api-refused-send>`);
**400** as above or for a missing field; **403** for a closed account; **429** when the ``auth_login`` throttle is exhausted or the address is locked out.


Email verification
==================

A new account and a member an administrator creates with a password are mailed a
link that proves the address::

    {SITE_URL}/portal/verify-email?token=<token>

The token is ``django.core.signing.dumps({"user": <id>, "email": <address>},
salt="accounts.email-verification")``, with the address stripped and
lowercased.  It is checked with ``max_age=EMAIL_VERIFICATION_TIMEOUT`` seconds
(three days by default; see :doc:`configuration`).  Because the address is
signed into it, changing the address makes every earlier link useless, while a
change of capitalization alone does not.

``apps.accounts.services.send_email_verification`` renders
``templates/emails/email_verification.{txt,html}`` with the subject
``"<organization name>: verify your email address"``, and the email log
records it under the purpose ``email_verification``.

A change of address is proved by a link of its own, to the same page and endpoint,
before it takes effect (`Changing the address`_).

``POST /auth/email/verify``
---------------------------

Follows a link mailed to prove an address: a verification link, or the link that
completes a change of address.  Open to anonymous callers, because the mail client
may open the link in a browser that has no session.

.. code-block:: json

   {"token": "eyJ1c2VyIjoxMiwiZW1haWwiOiJtYXJ0YUBleGFtcGxlLm9yZyJ9:1xAG4w:..."}

.. code-block:: json

   {"email": "marta.reyes@example.org", "changed": false}

``email`` is the address the link proved, which the account signs in with, and
``changed`` is true when following the link moved the account to it.
``apps.accounts.email_change.follow_verification_link`` tells the two kinds of link
apart by their signing salts.

For a verification link, the account the token names is stamped verified and an
``account.email_verified`` audit line is written; any bounce recorded against the
address is cleared, since mail to it has just arrived.  A link mailed when somebody
registered with a donor's address first upgrades the donor to the member or
friend that registration asked for (see `POST /auth/register`_), and needs a
``password``, the one the account will sign in with, chosen by whoever follows the
link:

.. code-block:: json

   {"token": "eyJ1c2VyIjo0MSwiZW1haWwiOiJnaXZlckBleGFtcGxlLm9yZyJ9:1xAG4w:...",
    "password": "..."}

Without it the answer asks for one and nothing changes, so the portal shows a
password form and posts again::

    400 {"password": ["Choose a password to finish opening your account."],
         "code": "password_required"}

A password Django's validators reject is a ``400 {"password": [...]}``, and nothing
changes either.  ``password`` is ignored for every other link, and nobody is signed
in.  A donor's link that carries no upgrade is refused like a forged one.

A link that completes a change of address is described under `Changing the
address`_.  Following any link a second time answers 200 again and changes nothing.
Every way a link can be unusable — a forged or mangled token, one older than the
timeout, a deactivated or deleted account, an address the account no longer holds,
a change of address since replaced or undone — returns the same
``400 {"token": ["That verification link is invalid or has expired."]}``.  A change
whose new address another account has taken meanwhile is
``400 {"token": ["Another account already uses that email address."]}``, and
nothing changes.

Statuses: **200**; **400** for an unusable token, a missing field, or a donor's
link with no password or a rejected one; **429** when the ``auth_verify`` throttle
is exhausted.

``POST /auth/email/resend``
---------------------------

Mails the signed-in account a fresh link.  No body.  While a change of address is
waiting, the link that completes it goes to ``pending_email`` once the answer has gone
(``apps.accounts.email_change.send_email_change_link``, which sends nothing to an
address another account holds, the answer the same either way); otherwise a
verification link goes to the account's own address.  The answer names the address:

.. code-block:: json

   {"detail": "Verification message sent to marta.reyes@example.org."}

A verified address with no change waiting is refused, and nothing is mailed::

    400 {"detail": "Your email address is already verified."}

Statuses: **202**, also when the mail server refuses the message
(:ref:`refused sends <api-refused-send>`); **400** for a verified address with no
change waiting; **401** when anonymous; **429** when the ``auth_verify_resend``
throttle is exhausted.


.. _api-email-change:

Changing the address
--------------------

The address is the login and where a password reset link goes, so a change never
takes effect on the word of whoever asked: a stolen session must not be able to move
the account to its own mailbox unseen.  ``apps.accounts.email_change`` holds the
whole flow.

#. **The request.**  ``request_email_change(actor, target, email)`` stores the new
   address as the account's ``pending_email``, replacing any earlier one, and audits
   ``action=account.email_change_request actor=<who asked> target=<id>``.  Nothing
   about signing in changes: the account keeps its ``email``, its verification and
   its password.  An address equal to the current one, compared case-insensitively,
   is no change at all.  Otherwise the account-edit guard (:ref:`account-edit-guard`)
   runs first; then the account's own request is refused while it keeps a recovery
   address (below); then an address another account holds, or keeps as its recovery
   address (``apps.accounts.services.address_taken``), is refused with *Another
   account already uses that email address.* -- except on the account's own request,
   which goes on exactly as for a free address (stored as pending, shown by
   ``/auth/me``, resent by ``/auth/email/resend``, the old address told) except that
   no link is ever mailed to an address another account holds, so that a session
   cannot be used to find out who has an account.  An account administrator's own
   address is not changed on the member record, which asks for no password: that is
   refused against ``email`` with *Change your own address from Change email, which
   asks for your password.*
   ``POST /auth/email/change`` below asks for the account itself, and
   ``PATCH /admin/members/{user_id}`` for an account administrator
   (:doc:`api-members`).
#. **The link to the new address.**  Once the request commits -- or, for
   ``POST /auth/email/change``, once its answer has gone
   (:ref:`mail after the answer <api-after-response>`), as for the notice below --
   ``pending_email`` is mailed *confirm your new email address*
   (``templates/emails/email_change_confirm.{txt,html}``) with a link to
   ``/portal/verify-email``; the message does not show the address the account signs
   in with.  Its token is ``django.core.signing.dumps({"user": <id>, "email": <current
   address>, "change_to": <new address>, "by": <id of who asked>, "pw": <password
   fingerprint>}, salt="accounts.email-change")``, the addresses normalized, read with
   the same ``EMAIL_VERIFICATION_TIMEOUT``.  Nothing is sent to an address another
   account holds or keeps for recovery (``send_email_change_link``).  The fingerprint is a keyed HMAC of the
   stored password hash (``email_change.password_fingerprint``), as Django signs a
   password reset link over it, so any new password spends the link.  Every write of a
   new or unusable password also empties ``pending_email``:
   ``accounts.services.replace_password`` (a change and a reset) and
   ``accounts.status.clear_password_and_end_sessions`` (``create_admin`` taking an
   account back, and **Require a new password**), and so does every deactivation.
#. **The notice.**  The recovery address, while the account keeps one, or else the
   current address when it is verified, is mailed *your email address is changing*
   (``templates/emails/email_change_notice.{txt,html}``), naming the new address and
   carrying a link that undoes the change.  An address nobody has verified is told
   nothing: it may belong to somebody else entirely, who must not be handed a link
   that takes the account.
#. **Completing.**  Following the link (`POST /auth/email/verify`_) works only while
   the account is active, still holds the address the token names, still waits for
   the address the link was sent to, and still has the password it had when the link
   was made; a later request, an undo, a new password, or any other change of address
   spends it.  It writes ``pending_email`` as the account's ``email``, as it was
   typed, empties ``pending_email``, stamps the address verified now, and clears any
   bounce recorded against the old one.  It is audited as the account's own
   ``account.update`` of ``email`` and ``account.email_verified``, recorded in the
   account's history as ``email_changed`` under the account that asked for it
   (`GET /admin/users/{id}/history`_), and raises the ``email_changed`` event with the
   old address (:doc:`notification-events`).  The answer's ``changed`` is true.  An
   address another account took meanwhile, checked first and caught again as the
   unique constraint's ``IntegrityError`` when two complete at once, is a 400 and
   changes nothing; completing takes the address lock registration and the donation
   checkout take (``accounts.services.lock_address``), so neither makes an account
   with the address meanwhile.  Sessions are left alone.
#. **The recovery address.**  A completed change keeps the verified address it left
   as ``recovery_email`` until ``recovery_until``, ``EMAIL_CHANGE_UNDO_TIMEOUT``
   seconds (seven days, as long as an undo link lasts); while one is kept already, it
   stays and is kept that long from now.  Meanwhile the address is reserved for the
   account: registration (``POST /auth/register`` treats it as the account's own,
   and its notice points to the undo link and the office rather than to signing in),
   the public donation checkout (the gift goes to the account, its receipt to the
   recovery address), every other account's change of address and New member, and
   ``create_admin`` treat it as taken.  The account's own address cannot change again
   by self-service; an account administrator may still change it, and the notices go
   to the recovery address, as does a copy of the *your password was changed* notice,
   with an undo link.  The Django admin shows ``email`` read-only, and the Wagtail
   account screens are closed, so no form changes an address around this flow.  Once it commits, the recovery address is
   mailed *your email address has changed*, with a fresh undo link.
#. **Undo.**  `POST /auth/email/undo`_ below.

A donor cannot sign in, so a donor's address is only where receipts go: an account
administrator's change of it is written at once, audited as ``account.update`` of
``email``, and nothing is mailed.

``POST /auth/email/change``
---------------------------

Asks to move the signed-in account to another address and returns the user payload,
``email`` unchanged and ``pending_email`` the address asked for.  The address is the
login, so the current password is asked for first.

.. code-block:: json

   {"email": "marta@example.net", "current_password": "..."}

A box left empty is refused first, with *Enter the new address.* or *Enter your
current password.*, and an address that does not parse with *Enter an email
address, such as name@example.org.*  The checks then run in this order and only
the first failure is reported, each a 400 keyed on its field:

* ``{"current_password": ["That is not your current password."]}``
* ``{"email": ["That is already your email address."]}`` — compared
  case-insensitively.
* ``{"email": ["Your sign-in address changed in the last seven days, so it cannot
  change again until 10/19/2026."]}`` — while the account keeps a recovery address,
  naming the day it stops being kept.

An address another account holds is not refused, and is handled exactly as a free one:
the same answer, ``pending_email`` stored and shown by ``GET /auth/me``, the same
answer from ``POST /auth/email/resend``, the same notice to the current address.  The
only difference is that no link is ever mailed to it, and both messages are sent after
the answer has gone, so its timing does not differ either.  The change simply never
completes.

The request goes through ``request_email_change`` with the account as both actor
and target, described under `Changing the address`_; it is audited as
``action=account.email_change_request actor=12 target=12``.  The session survives.
Asking again with another address replaces the one waiting, and the earlier link
stops working.

Statuses: **200**, also when the mail server refuses either message
(:ref:`refused sends <api-refused-send>`); **400** for any rejection above or a
missing field; **401** when anonymous; **429** when the ``auth_email_change``
throttle is exhausted.

``POST /auth/email/undo``
-------------------------

Follows the link in a notice to the old address, and undoes the change it was mailed
about.  Open to anonymous callers, and throttled under ``auth_verify``.  The link is
``{SITE_URL}/portal/undo-email-change?token=<token>``, the token
``django.core.signing.dumps({"user": <id>, "from": <old address>, "to": <new
address>, "at": <when it was made>}, salt="accounts.email-change-undo")``, the
addresses as they were stored.  It is good for
``apps.accounts.email_change.EMAIL_CHANGE_UNDO_TIMEOUT`` seconds, seven days.  The
portal's page posts the token only when the visitor presses **Undo the change**, so a
mail scanner that opens the link changes nothing.

.. code-block:: json

   {"token": "eyJ1c2VyIjoxMiwiZnJvbSI6Im1hcnRhQGV4YW1wbGUub3JnIn0:1xAG4w:..."}

.. code-block:: json

   {"email": "marta.reyes@example.org", "taken": false}

In one transaction, holding a lock on the account's row
(``apps.accounts.email_change.undo_email_change``):

#. when the account no longer holds the old address, it is put back and stamped
   verified, since the link could only have reached its owner, and any bounce is
   cleared;
#. any change still waiting is dropped, and the recovery address is forgotten;
#. the password is made unusable, so whoever asked for the change, who knew it,
   cannot sign in again, and every session signed in to the account is ended
   (``accounts.status.end_sessions``);
#. ``email_change_undone_at`` is set to now, audited as
   ``action=account.email_change_undo actor=12 target=12 restored=<true or false>``,
   and recorded in the account's history as ``email_change_undone``;
#. once it commits, the address the undo link was mailed to is sent a password reset
   link, which is how the owner signs in again.  The account's active flag is left
   alone; completing that reset reactivates a deactivated account, as any reset does.

When another account holds the old address by then -- the reservation makes this rare
-- it cannot be put back, and the account still signs in with an address whose holder
could reset its password.  The answer's ``taken`` is true, and the account is closed
instead of being handed back: everything above is done except putting the address
back and mailing the reset link, and the account is also deactivated and blocked from
reactivating (its mandates canceled and terms suspended, as any deactivation does),
audited as ``account.deactivate`` and ``account.block`` under the account, recorded in
its history, and raised as ``account_deactivated``, which reaches the user
administrators subscribed to it.  No sign-in, reset, or registration brings it back
until a user administrator lifts the block; the page asks the owner to contact the
office.

Each link works once: an undo spends every undo link made before it, because a token
older than ``email_change_undone_at`` is refused.  While the account keeps a recovery
address, only a link mailed to that address counts, so whoever moved the account can
never follow an undo link of their own that spends its owner's; and since the
account's own address cannot change again meanwhile, they cannot be sent one.

* **400** ``{"token": ["That link is invalid, has expired, or has been used."]}`` —
  a forged or mangled token, one older than seven days, one spent by an earlier
  undo, one for no account or a donor's, or one mailed to another address than the
  recovery address the account keeps.

Statuses: **200**; **400** as above or for a missing field; **429** when the
``auth_verify`` throttle is exhausted.

Unverified sessions
-------------------

A signed-in account whose ``email_verified`` is false may call only these:

* the endpoints an anonymous visitor may call: ``GET /auth/csrf``,
  ``POST /auth/login`` and its three two-factor steps, ``POST /auth/register``,
  ``POST /auth/password/reset``, and ``POST /auth/password/reset/confirm``;
* ``GET /auth/me`` and ``POST /auth/logout``;
* ``POST /auth/email/verify``, ``POST /auth/email/resend``,
  ``POST /auth/email/change``, and ``POST /auth/email/undo``;
* ``GET /site/config``.

Every other request under ``/api/v1/``, read or write, is answered::

    403 {"detail": "Verify your email address to continue.", "code": "email_unverified"}

The check is ``apps.accounts.middleware.EmailVerificationGateMiddleware``,
installed after ``AuthenticationMiddleware``.  It runs before the view, matches the
allowed routes by their URL names (``UNVERIFIED_ALLOWED_VIEWS``), and leaves an
anonymous request, a verified account, and every path outside the API alone, so
the user guide at ``/docs/`` stays readable.  It is enforced on the server, not
only by the portal's screens: an unverified account cannot read or change its
profile, pay, or open an administrative endpoint by calling the API directly.
Following the link, or an administrator's resend being followed, opens the rest
of the API on the next request.


Roles
=====

``GET /roles``
--------------

The role catalog, in privilege order, for any authenticated caller.  It is a
bare array rather than a paginated envelope: there are nine roles and there
will not be many more.

.. code-block:: json

   [{"slug": "member",
     "description": "A member or a friend with a portal account."},
    {"slug": "verifier",
     "description": "Verify a member's pilot certificate, medical, and photo ID, and an aircraft's insurance, from the member check and the aircraft check."},
    {"slug": "dart_leader",
     "description": "Look up any member and see membership, medical, certificate, and aircraft insurance currency, and send bulk email to the members and friends of the DART on their own profile."}]

Descriptions live in ``apps.accounts.roles.ROLE_DESCRIPTIONS``, which is also
what ``manage.py seed_roles`` iterates, so the API, the seed and the portal's
role checkboxes can never drift apart.

Statuses: **200**; **401** when anonymous.


Users admin
===========

All twelve endpoints require the ``user_admin`` role.  ``system_admin`` passes
every role check, so system administrators have them too; every other role gets
403.

``GET /admin/users``
--------------------

Paginated list of user payloads, ordered by last name, first name, email.
Each row also carries ``email_verified_at``: when the owner last proved the
address, as an ISO datetime, or ``null`` while it is unverified; and
``reactivation_blocked``, true while a user administrator has blocked the account
from reactivating (:ref:`api-reactivation-block`).  ``email_bounced_at`` is when
the bounce check last found the address bouncing, as an ISO datetime, or ``null``
while no bounce is known, and ``email_bounce_detail`` that report's status code and
diagnostic, or ``""`` (:ref:`email-bounces`).  ``two_factor_enabled`` is true
while the account has a confirmed authenticator device (:ref:`api-two-factor`),
read from an ``Exists`` annotation so the page costs no query per row, and
``can_reset_two_factor`` is true when the caller may reset it
(:ref:`api-reset-two-factor`), which the user record reads to gray its button out.
``phone``, ``dart`` (the DART's
name), ``city``, ``county``, and ``home_airport`` (the home airport's identifier) are
read from the profile for the columns the Roles list can show; each is
``""``, and ``dart`` is ``null``, for an account with no profile or no DART.

.. code-block:: json

   {
     "count": 137,
     "next": "http://localhost:8000/api/v1/admin/users?page=2",
     "previous": null,
     "results": [
       {"id": 12, "email": "marta.reyes@example.org", "first_name": "Marta",
        "last_name": "Reyes", "roles": ["member", "dart_leader"],
        "is_active": true,
        "membership": {"status": "current", "expires_on": "2027-06-30",
                       "plan": "Annual", "is_lifetime": false},
        "profile_complete": true, "email_verified": true, "kind": "member",
        "friend_on": null,
        "email_verified_at": "2026-09-01T10:14:02.100522-07:00",
        "email_bounced_at": null, "email_bounce_detail": "",
        "reactivation_blocked": false, "two_factor_enabled": false,
        "phone": "415-555-0100",
        "dart": "Palo Alto", "city": "Palo Alto", "county": "Santa Clara",
        "home_airport": "PAO"}
     ]
   }

=================  ============================================================
Parameter          Effect
=================  ============================================================
``search``         Case-insensitive match on first name, last name and email.
                   Terms are ANDed, so ``Ada Lovelace`` matches one person.
``role``           One role slug.  An unknown slug is a 400, not an empty page.
``is_active``      ``true`` / ``false``.
``kind``           ``member``, ``friend``, or ``donor``, as stored.  An
                   unknown kind is a 400.  This list is where a donor's
                   account is found; donors appear in no member list.
``email_bounced``  ``true`` keeps the accounts whose address has a bounce
                   recorded, ``false`` the rest.
``ordering``       One of ``last_name``, ``first_name``, ``email``,
                   ``is_active``, ``created_at``; prefix with ``-`` to reverse.
                   Unlike ``role``, an unrecognized field is *ignored* rather
                   than rejected, so a typo silently gives you the default
                   order.
``page``,          Standard pagination.
``page_size``
=================  ============================================================

Statuses: **200**; **400** for an unknown ``role`` slug or ``kind``; **401** when
anonymous; **403** without ``user_admin``; **404** for a ``page`` past the
end.

``GET /admin/users/{id}``
-------------------------

One user payload as the list returns it, plus two facts about the account's terms that
the user record words the membership by, since a user administrator cannot read the
terms themselves: ``has_terms`` (any term at all) and ``has_suspended_term`` (a
deactivation set one aside).  ``assignable_roles`` lists the role slugs the caller may
grant or take away on this account, in privilege order, under the rules of
``PATCH`` below (``accounts.services.assignable_roles``): every slug for a system
administrator, the unguarded roles plus the guarded ones the caller holds for anybody
else, and none at all on the caller's own account.  The user record grays out every
other box.  ``PATCH`` and the account status actions below answer in this shape too;
the list leaves the three out, since each costs a query per row or depends on the
caller and the row together.

Statuses: **200**; **401** when anonymous; **403** without ``user_admin``;
**404** for an unknown id.

``PATCH /admin/users/{id}``
---------------------------

Accepts ``roles`` alone, and returns the updated payload.  The user record changes
roles only: the names and the address are changed through
``PATCH /admin/members/{user_id}`` (:doc:`api-members`) or by the person.  A body
carrying ``first_name``, ``last_name``, or ``email``, even with the value the account
already has, is a **400** keyed on each one it carries, and nothing is saved:

.. code-block:: json

   {"email": ["The user record changes roles only. A name or an email address is changed on the member record, or by the person themselves."]}

``PUT`` and ``DELETE`` are 405:
this API edits accounts, it does not replace or remove them.  Deleting a member
is ``DELETE /admin/members/{user_id}``, behind ``account_admin`` — see
:doc:`api-members`.

.. code-block:: json

   {"roles": ["member", "dart_leader"]}

.. code-block:: json

   {"id": 12, "email": "marta.reyes@example.org", "first_name": "Marta",
    "last_name": "Reyes", "roles": ["member", "dart_leader"],
    "is_active": true,
    "membership": {"status": "current", "expires_on": "2027-06-30",
                   "plan": "Annual", "is_lifetime": false},
    "profile_complete": true, "email_verified": true, "kind": "member",
    "friend_on": null,
    "email_verified_at": "2026-09-01T10:14:02.100522-07:00",
    "email_bounced_at": null, "email_bounce_detail": "",
    "reactivation_blocked": false}

``email_verified_at``, ``email_bounced_at``, ``email_bounce_detail``, ``kind``,
``friend_on``, ``is_active``, ``reactivation_blocked`` and ``two_factor_enabled``
are read-only here: an
``is_active`` sent in the body is ignored.  The kind is the account administrator's to change (:doc:`api-members`),
never the user administrator's, and the two flags change only through the
account status actions (:ref:`api-account-status`).

A **Deleted member <id>** tombstone, which keeps a deleted account's payments,
takes no edit at all: the view refuses any body with **400** ``{"detail": "This
record keeps a deleted member's payments in the books and cannot be changed."}``
before the serializer runs, as the member record does
(:ref:`api-members-tombstone`).

Four rules are enforced on ``roles``, the first in ``AdminUserSerializer`` and the
rest in ``accounts.services.update_account``, which every role write passes through:

**Role slugs are validated.**  Anything outside ``ROLE_SLUGS`` is a 400 on
``roles``.  The list you send replaces the account's role groups exactly, and it
comes back sorted into privilege order.  Group memberships that are not roles —
Wagtail's editor groups, say — are left alone.  A list matching the groups the
account already holds is not a write: the groups and the Django flags are left
exactly as they are, so the portal may post the whole form on every save.

**Only a system administrator may move ``system_admin``.**  A write of the role
list moves it when the list checks ``system_admin`` on an account whose groups
lack it, or leaves it unchecked on an account that counts as a system
administrator.  From a caller who is not one, that is a 400 on ``roles``.  The
second half of the test reads *effective* roles, so a Django superuser without
the role group counts as a system administrator, and so does the caller who
holds the flag rather than the group.  A user administrator can therefore still
edit a system administrator's *other* roles, as long as ``system_admin`` stays
in the list — but no role list of a ``createsuperuser`` account is open to them,
because writing one rebuilds the flags from that list alone: leaving the role
out would take the superuser flag away, and putting it in grants the group.

Granting or revoking ``system_admin`` also syncs the Django flags, because a
system administrator is a Django superuser::

    user.is_superuser = "system_admin" in roles
    user.is_staff     = user.is_superuser or "website_admin" in roles

``website_admin`` is in that second line so an unrelated role edit cannot take
the Wagtail admin away from a website administrator.

**A guarded role moves only for its holder.**  ``GUARDED_ROLES`` in
``accounts.roles`` are the two-factor roles: ``user_admin``, ``treasurer``,
``account_admin``, ``management``, ``website_admin``, and ``system_admin``.  A write
that grants or takes away one the caller does not hold (by effective roles) is a 400
on ``roles`` naming every such role, in privilege order, and nothing in the list is
saved:

.. code-block:: json

   {"roles": ["You cannot give or take away a role you do not hold yourself: Treasurer, CalDART management."]}

A system administrator, a Django superuser among them, holds every role, so may move
any of them.  ``member``, ``verifier``, and ``dart_leader`` are open to every caller of
the endpoint, on any account; a guarded role the target keeps is no obstacle.

**Nobody changes their own roles**, a system administrator included.  A write that
would change the caller's own role list is a **403**, audited with
``reason=own_account``, and nothing is saved; resending the list the caller already
holds is no change and answers 200:

.. code-block:: json

   {"detail": "You cannot change your own roles. Ask another administrator."}

The rules run with the slugs first, then your own account, then ``system_admin``,
then the guarded roles, so a write that breaks several is refused by the first.
Every refusal after the slugs writes a WARNING audit line ``action=account.roles``
with ``reason=own_account``, ``system_admin_role``, or ``roles_not_held``.  A write
that goes through is audited as ``account.roles`` with the slugs ``added`` and
``removed`` and raises ``roles_changed`` (:doc:`notification-events`).  The Django
admin shows ``groups``, ``is_superuser``, ``is_staff``, and ``user_permissions``
read-only, and offers no group screens at all (``Group`` is unregistered), so roles
change only through ``accounts.services.update_account``: this endpoint, the member
check's verifier toggle, and ``create_admin``.  A role write locks the account's row
first, so two role writes to one account run one after the other.

Statuses: **200** with the updated payload; **400** for an unknown role slug,
a move of ``system_admin`` by a caller who is not one, a move of a guarded role
the caller does not hold, or a name or address in the body; **401** when anonymous;
**403** without ``user_admin``, or for a change to your own roles; **404** for an
unknown id; **405** for ``PUT`` and ``DELETE``.

``POST /admin/users/{id}/send-password-reset``
----------------------------------------------

Sends the same email as ``/auth/password/reset``, but this one reports what
happened, because the caller is a trusted administrator rather than an
anonymous visitor.  There is no request body.

.. code-block:: json

   {"detail": "Password reset email sent to marta.reyes@example.org."}

An account with nobody to mail is refused::

    400 {"detail": "That account is deactivated, so no reset email was sent."}

Two accounts have nobody to mail: a deactivated one, and one that holds no
email address.  Both are refused with that one sentence, so a caller who sees
it on an active account should check the address on the member record.  Three
more are refused first, in this order, each with a sentence of its own: a donor, who
cannot sign in; the caller's own account, whose password is changed on Change
password; and an account holding roles the caller does not hold, under the
:ref:`account-edit guard <account-edit-guard>`::

    400 {"detail": "A donor cannot sign in, so no reset email was sent."}
    400 {"detail": "You cannot send a password reset to your own account. Use Change password instead."}
    400 {"detail": "You cannot send a password reset to an account that holds roles you do not hold."}

Both the send and the refusal are recorded in the audit log
(:ref:`deploy-audit-log`), a refusal as ``action=password_reset.admin_sent`` with
``reason=donor_account``, ``own_account``, ``roles_not_held``, or
``inactive_account``.  A mail server that refuses the message is a 503
naming the Sent emails page, and nothing is recorded in the audit log
(:ref:`refused sends <api-refused-send>`).

Statuses: **200** when the mail went out; **400** for an account that is
deactivated, holds no email address, is a donor's, is the caller's own, or holds
roles the caller does not hold; **401** when anonymous;
**403** without ``user_admin``; **404** for an unknown id; **503** when the mail
server refused the message.  This endpoint is not
throttled —
the throttles guard the anonymous routes.

.. _api-require-new-password:

``POST /admin/users/{id}/require-new-password``
-----------------------------------------------

For an account somebody other than its owner may know the password to.  No body.
``accounts.api.account_actions.require_new_password_for`` makes the account's password
unusable and ends every session signed in to it
(``accounts.status.clear_password_and_end_sessions``, which ``create_admin`` uses too),
in one transaction under a lock on the account's row.  Then the ``password_reset``
email goes to the address the account holds now, sent with
``send_password_reset_email(..., required=True)``: its subject is ``<organization
name>: choose a new password``, and its bodies say that an administrator has required
a new password, that the old one no longer works and every session was ended, and that
nobody can sign in until the link is used, in place of the self-service wording that
says the password has not changed.  Afterwards the old password signs nobody in,
``/auth/reactivate`` refuses it, and every reset link made before is spent, because
Django's reset token is built from the password hash.  A password change or reset
already in flight is refused too, since ``accounts.services.replace_password`` writes
only over the hash the request checked, and an account edit made from a copy read
earlier saves only the columns it changed.  The owner's way back is the mailed link,
or **Forgot password** on the sign-in page.  The link goes to whatever address the
account holds, which somebody who took the account over may have changed; the portal's
confirmation names it, so the administrator can have it corrected on the member
record first.

.. code-block:: json

   {"detail": "The old password no longer works and every session is ended. A password reset email went to marta.reyes@example.org."}

The active flag and the reactivation block are left alone.  A deactivated account stays
deactivated and is mailed the link all the same: confirming it at
``/auth/password/reset/confirm`` sets the new password and reactivates the account, as
any reset of a deactivated account does.  A blocked account is mailed nothing, since
the confirmation would refuse its link, and the answer's second sentence reads "The
account is blocked from reactivating, so no reset email was sent."  Once the block is
lifted, the owner asks for a reset themselves.  Requiring a new password again repeats
everything and mails a fresh link.

Refused, changing nothing, in this order::

    400 {"detail": "A donor cannot sign in, so there is no password to replace."}
    400 {"detail": "You cannot require a new password for your own account. Use Change password instead."}
    400 {"detail": "You cannot require a new password for an account that holds roles you do not hold."}

A tombstone is a donor, so the first sentence covers it; the last is the
:ref:`account-edit guard <account-edit-guard>`.  Each refusal is recorded at WARNING as
``action=account.new_password`` with ``reason=donor_account``,
``own_account``, or ``roles_not_held``; the change itself is recorded at INFO as
``action=account.new_password actor=<admin> target=<id>`` and as a
``new_password`` entry of the account's history.  A mail server that refuses the reset
email is a 503 whose ``detail`` says the password was shut out and the sessions ended
regardless, and asks for the action to be pressed again once the server is fixed; the
failed send is in the email log and the refusal is logged
(:ref:`refused sends <api-refused-send>`).

Statuses: **200** once the password is shut out, whether or not a link was mailed;
**400** for a donor, your own account, or an account holding roles you do not hold;
**401** when anonymous; **403** without ``user_admin``; **404** for an unknown id;
**503** when the mail server refused the reset email.  Not throttled.

``POST /admin/users/{id}/send-email-verification``
--------------------------------------------------

Mails the account a fresh verification link on an administrator's behalf.  No
body.

.. code-block:: json

   {"detail": "Verification message sent to marta.reyes@example.org."}

Three accounts are refused, and none is mailed::

    400 {"detail": "A donor cannot sign in, so no verification message was sent."}
    400 {"detail": "That address is already verified."}
    400 {"detail": "That account is deactivated, so no verification message was sent."}

The send is recorded in the audit log as
``action=email_verification.admin_sent actor=<admin> target=<id>``.  A mail
server that refuses the message is a 503 naming the Sent emails page, and
nothing is recorded in the audit log (:ref:`refused sends <api-refused-send>`).

Statuses: **202** when the mail went out; **400** for a donor, a verified
address, or a deactivated account; **401** when anonymous; **403** without ``user_admin``;
**404** for an unknown id; **503** when the mail server refused the message.  Not
throttled.

.. _api-clear-bounce:

``POST /admin/users/{id}/clear-bounce``
---------------------------------------

Clears the bounce the bounce check recorded against the account's address
(:ref:`email-bounces`), for an address the administrator has confirmed works.  No
body.  ``email_bounced_at`` and ``email_bounce_detail`` are emptied, the change is
recorded in the audit log as ``action=account.bounce_cleared actor=<admin>
target=<id>``, and the answer is the user payload as it stands afterwards.  An
account with no bounce recorded is answered unchanged, and nothing is recorded.
The flag comes back if the next message to the address bounces too.

Statuses: **200** with the user payload; **401** when anonymous; **403** without
``user_admin``; **404** for an unknown id.

.. _api-reset-two-factor:

``POST /admin/users/{id}/reset-two-factor``
-------------------------------------------

Takes away the account's two-factor sign-in, for a person who lost their phone and
their backup codes.  No body.  In one transaction holding a lock on the account's
row (``accounts.api.account_actions.reset_two_factor_for``), the device and every
backup code are deleted, every unexpired session signed in to the account is
deleted (``accounts.status.end_sessions``), the reset is recorded as
``action=account.mfa_reset actor=<admin> target=<id>`` and as an ``mfa_reset``
history entry, and once it commits the person is mailed a notice
(``mfa_reset``).  The answer is the user payload as it stands afterwards, with
``two_factor_enabled`` false.  The person sets two-factor sign-in up again at
their next sign-in, which insists on it when a role requires it
(:ref:`api-two-factor`).  An account with nothing set up is reset all the same:
its sessions end and the reset is recorded.

Refused with **400** ``{"detail": ...}``, changing nothing, in this order: a
tombstone (the member record's sentence, :ref:`api-members-tombstone`), a donor
("A donor has no portal account to reset."), your own account ("You cannot reset
your own two-factor sign-in. Turn it off or on yourself."), and an account
holding the System administrator role, or a superuser's, when you are not a system
administrator ("Only a system administrator can reset a system administrator's
two-factor sign-in.").  Any other account may be reset whatever roles it holds: a
user administrator resets a treasurer's lost phone.  Each refusal is recorded at
WARNING as ``action=account.mfa_reset`` with the reason ``tombstone``,
``donor_account``, ``self_deactivation``, or ``system_admin_target``.
``manage.py reset_two_factor --email ADDRESS`` does the same from the server, as a
system administrator would, and also forgets the address's counted failed sign-ins
(:ref:`api-login-lockout`).

Statuses: **200** with the user payload; **400** for a refusal; **401** when
anonymous; **403** without ``user_admin``; **404** for an unknown id.


``GET /admin/users/{id}/history``
---------------------------------

The account's role, status, and address changes, newest first, unpaginated: the user
record's History card.  Each is an ``AccountChange`` row (``apps.accounts.history``),
written beside the audit line for the same change, since the audit log is a journal and
cannot be read back.  A row is written for an account created on New member
(``created``), a role list that really changes (``roles``), each deactivation,
reactivation, block, and lifted block (``deactivated``, ``reactivated``, ``blocked``,
``unblocked``), including the owner's own deactivation and reactivation, each new
password required (``new_password``), each change of address completed or undone
(``email_changed``, under the account that asked for it, and ``email_change_undone``,
under the account itself; see `Changing the address`_), and each two-factor reset
(``mfa_reset``).  Neither address is stored.

.. code-block:: json

   [
     {"id": 7, "changed_at": "2026-10-04T15:12:00-07:00",
      "changed_by": {"id": 3, "name": "Nina Kowalski"}, "by_command": false,
      "kind": "roles", "added": ["dart_leader"], "removed": []},
     {"id": 2, "changed_at": "2026-09-01T10:00:00-07:00",
      "changed_by": null, "by_command": true, "kind": "deactivated",
      "added": [], "removed": []}
   ]

``changed_by`` is the acting account's id and name, which is the account itself for
its owner's own change, and ``null`` for a management command (``by_command`` true,
read as *The system*) or an account since deleted (``by_command`` false, read as *A
deleted account*).  ``added`` and ``removed`` are the role slugs a ``roles`` row granted and
took away, in privilege order, and empty for every other kind.

Statuses: **200**; **401** when anonymous; **403** without ``user_admin``;
**404** for an unknown id.


.. _api-account-status:

The account's status
--------------------

Four endpoints change whether an account can sign in.  None takes a body, and
each answers 200 with the user payload above as it stands afterwards.  Each runs
in one transaction holding a lock on the account's row
(``accounts.api.account_actions``), so two administrators acting at once take
turns.  A refusal is a 400 ``{"detail": "<sentence>"}`` and changes nothing; the
sentences are listed under :ref:`account-edit-guard`.

``POST /admin/users/{id}/deactivate``
   Everything ``POST /auth/deactivate`` does, under the administrator
   (``accounts.status.deactivate_account``): ``is_active`` is cleared and any change
   of address waiting dropped,
   ``account.deactivate`` is recorded with the administrator as actor, the
   ``account_deactivated`` event is raised naming them, and every unexpired
   session signed in to the account is deleted (``accounts.status.end_sessions``);
   then every active or paused mandate is canceled with the administrator as
   ``canceled_by`` (a pending one discarded), and every term with time left is
   suspended, each ``membership.correct`` recorded under the administrator.
   Refused for your own account, a donor, an account holding roles you do not
   hold, and an account already deactivated.

``POST /admin/users/{id}/reactivate``
   Everything ``POST /auth/reactivate`` does, under the administrator
   (``accounts.status.reactivate_account``), except signing anybody in:
   ``account.activate`` and ``account_reactivated`` name the administrator, each
   suspended term is restored, and an unverified address is mailed a link (a
   refused link leaves the answer unchanged,
   :ref:`refused sends <api-refused-send>`).
   Refused for a donor, an account holding roles you do not hold, an account
   blocked from reactivating, and an account already active.

``POST /admin/users/{id}/block``
   Sets ``reactivation_blocked`` (:ref:`api-reactivation-block`), recorded as
   ``account.block``.  An active account is deactivated first, exactly as
   ``/deactivate`` does it.  Blocking an account already blocked changes
   nothing.  Refused for your own account, a donor, and an account holding roles
   you do not hold.

``POST /admin/users/{id}/unblock``
   Clears ``reactivation_blocked``, recorded as ``account.unblock``, and leaves
   the account deactivated for its owner to bring back.  The same refusals as
   ``/block``.

Statuses: **200** with the updated payload; **400** for a refusal; **401** when
anonymous; **403** without ``user_admin``; **404** for an unknown id.

The account administrator has ``/deactivate`` and ``/reactivate`` on the member
record too, behind ``account_admin`` (:doc:`api-members`); blocking is the user
administrator's alone.


.. _api-reactivation-block:

Blocking reactivation
=====================

A deactivated account normally comes back whenever its owner wants: by signing
in, through ``POST /auth/reactivate``, or by completing a password reset.
``User.reactivation_blocked`` closes all three doors.  Only a user administrator sets or clears it, through ``POST
/admin/users/{id}/block`` and ``/unblock`` above, and setting it on an active
account deactivates the account first, so a blocked account is always
deactivated.  While it is set:

* ``POST /auth/login`` and ``POST /auth/reactivate`` answer the right password
  with 403 ``{"detail": "This account has been closed. Contact CalDART to
  reopen it."}`` and no ``code``; a wrong password still gets the ordinary 400;
* ``POST /auth/password/reset`` mails nothing, and answers 204 as for any
  address;
* ``POST /auth/password/reset/confirm`` refuses a link mailed before the block
  with the same sentence under ``token``;
* ``POST /auth/register`` answers as for any address, and mails the address that
  the account has been closed (`POST /auth/register`_);
* an administrator's ``/reactivate`` is refused with "A user administrator has
  blocked this account from reactivating. Allow reactivation on its user record
  first."

The organization's name in the sentence comes from the site settings
(``accounts.status.closed_account_message``), ``CalDART`` until one is set.



.. _account-edit-guard:

The account-edit guard
======================

Two things an administrator could use to take an account over are guarded: the
email address, which is the login *and* where a password reset link is mailed,
and the account's status, since deactivating or blocking it locks its owner out.
The one administrator edit of the address, ``PATCH /admin/members/{user_id}`` in
:doc:`api-members`, asks for the change through
``accounts.email_change.request_email_change``, which runs every new address past
``accounts.services.check_account_edit`` first (`Changing the address`_);
``PATCH /admin/users/{id}`` above refuses the address outright.  The status actions — the user
record's ``/deactivate``, ``/reactivate``, ``/block`` and ``/unblock`` above and
the member record's ``/deactivate`` and ``/reactivate`` — apply the same rule in
``accounts.status``, and the user record's ``/require-new-password``, which shuts the
owner's password out, and ``/send-password-reset``, which mails a link that sets one,
apply it too.

The rule, in the order it is applied:

#. **Only a real change counts.**  An address that arrives carrying the value the
   account already has is not a change, so an administration form that resends
   every field is judged only on the fields it actually moves.  Email addresses
   are compared case-insensitively after stripping, exactly as the uniqueness
   constraint compares them.
#. **Nobody may deactivate or block their own account**, whatever roles they
   hold; ``POST /auth/deactivate`` (:ref:`api-deactivation`) is the one
   self-service path.
#. **Otherwise the actor must hold every guarded role the target holds**
   (``GUARDED_ROLES``, the two-factor roles; ``member``, ``verifier``, and
   ``dart_leader`` do not count).  A system administrator holds every role, so one
   always passes.

Both sides of that last comparison use *effective* roles:
``accounts.services.effective_roles`` adds ``system_admin`` whenever
``is_superuser`` is set.  An account created by ``manage.py createsuperuser``,
which sets the flag without adding the role group, is therefore protected — and
protects — like any other system administrator.

Worked through the roles: an account administrator may change the address of a
plain member, a DART leader, or a verifier, but not a user administrator's; a user
administrator may deactivate any of those three, or another user administrator, but
not an account administrator; and a system administrator may do either to anybody.
Only the two-factor roles count.  Names are outside the guard entirely.

What the guard measures is the write in front of it, against the roles the two
accounts hold when it arrives.  A user administrator cannot widen it by granting
themselves the role they lack, since nobody changes their own roles, nor by taking it
off the target: the only roles that protect an account are the guarded ones, which
they can neither grant nor take away without holding them.  An account holding one
stays out of their reach by either route.  Against an account
administrator the guard is absolute in one request as well as two, because
``PATCH /admin/members/{user_id}`` has no ``roles`` field at all.

An address that is not a real change, such as the stored one resent in another case,
asks for nothing, whoever sends it: the stored address stays exactly as it was.  A
real change the guard allows is a request, which the new address's owner completes
(`Changing the address`_).

A refused address is a 400 keyed on ``email``, the same shape as the ``roles``
guard, so a client can show it against the input it came from; a refused status
action is a 400 carrying ``detail``::

    400 {"email": ["<message>"]}
    400 {"detail": "<message>"}

==================  ==============================================================
Refused change      Message
==================  ==============================================================
Their address       You cannot change the email address of an account that holds
                    roles you do not hold.
Your own status     You cannot deactivate your own account.
Their status        You cannot activate or deactivate an account that holds roles
                    you do not hold.
Your own block      You cannot block your own account.
Their block         You cannot block or unblock an account that holds roles you
                    do not hold.
Your own password   You cannot require a new password for your own account. Use
                    Change password instead. (or *You cannot send a password reset
                    to your own account.*)
Their password      You cannot require a new password for an account that holds
                    roles you do not hold. (or *You cannot send a password reset to
                    an account that holds roles you do not hold.*)
A donor             A donor has no portal account to deactivate. (or *to
                    reactivate.*, or *to block.*)
A blocked account   A user administrator has blocked this account from
                    reactivating. Allow reactivation on its user record first.
No change           That account is already deactivated. (or *That account is
                    already active.*)
A system admin's    Only a system administrator can reset a system
two-factor          administrator's two-factor sign-in.
Own two-factor      You cannot reset your own two-factor sign-in. Turn it off or
                    on yourself.
==================  ==============================================================

Every refusal but the last also writes one WARNING record to the audit log
(:ref:`deploy-audit-log`)::

    action=account.update actor=12 target=3 fields=email reason=roles_not_held

Account ids, field names and a reason slug only: no address, and nothing else
that identifies a person.  A refused role change reads
``action=account.roles ... reason=own_account``, ``system_admin_role``, or
``roles_not_held``; a refused status action
reads ``action=account.deactivate``, ``account.activate``, ``account.block`` or
``account.unblock`` with ``reason=self_deactivation``, ``roles_not_held``,
``donor_account`` or ``reactivation_blocked``, and a refused
``/require-new-password`` reads ``action=account.new_password`` with
``reason=own_account``, ``roles_not_held``, or ``donor_account``, and a refused
``/send-password-reset`` reads ``action=password_reset.admin_sent`` with the same
reasons, or ``inactive_account``.  An action that goes through is
recorded the same way at INFO, under the administrator.  The self-service
endpoints record ``action=account.deactivate actor=12 target=12
self_service=true`` and ``action=account.activate actor=12 target=12
self_service=true``.


Rate limiting
=============

Login, reactivation, registration, both password-reset endpoints, the
email-verify and email-undo endpoints, the verification resend, a change of one's own
address, every endpoint that takes a two-factor code, and the public donation checkout
are throttled by client address.  The classes are in
``apps.accounts.throttling``; they subclass
``AnonRateThrottle`` but override ``get_cache_key`` so a session does not exempt
the caller — a signed-in caller's requests would otherwise carry a cookie and go
uncounted.

Rates come from the ``AUTH_THROTTLE_RATES`` setting rather than DRF's
``DEFAULT_THROTTLE_RATES``, which makes them easy to change per environment and
easy to switch off:

=======================  =========================  ===========================
Scope                    Default                    Environment variable
=======================  =========================  ===========================
``auth_login``           20/min                     ``AUTH_THROTTLE_LOGIN``
``auth_register``        10/hour                    ``AUTH_THROTTLE_REGISTER``
``auth_password_reset``  10/hour                    ``AUTH_THROTTLE_PASSWORD_RESET``
``auth_verify``          30/hour                    ``AUTH_THROTTLE_VERIFY``
``auth_verify_resend``   5/hour                     ``AUTH_THROTTLE_VERIFY_RESEND``
``auth_email_change``    10/hour                    ``AUTH_THROTTLE_EMAIL_CHANGE``
``donate``               10/hour                    ``AUTH_THROTTLE_DONATE``
``donate_confirm``       30/hour                    ``AUTH_THROTTLE_DONATE_CONFIRM``
``auth_mfa``             10/min                     ``AUTH_THROTTLE_MFA``
=======================  =========================  ===========================

``donate`` guards ``POST /donations/checkout``, and ``donate_confirm`` the two
calls that ask a provider about a gift, ``POST /donations/stripe/confirm`` and
``POST /donations/paypal/capture``.  The calls that read a gift or complete a mock
one are proven by the signed token that checkout answers (see
:doc:`api-payments`) and ask no provider, so they are not counted.  The signed-in
payment endpoints are limited per account instead (:ref:`configuration-payment-limits`).

A scope mapped to ``None`` — or missing from the dict — is inert.
``caldart/settings/test.py`` maps every scope to ``None`` so the suite never
races a shared counter; the throttling tests turn one back on with
``override_settings`` and clear the cache around themselves.

An exceeded throttle is DRF's usual **429** with a ``Retry-After`` header.

``auth_mfa`` covers the code steps of signing in and the signed-in two-factor
endpoints alike; a pending sign-in also ends after five wrong codes.  The Wagtail
and Django admins serve no login form to throttle: both send the reader to the
portal's sign-in (:ref:`api-two-factor`).

.. _api-login-lockout:

The sign-in lockout
-------------------

The throttles count by client address; ``apps.accounts.lockout`` also counts by
the account signed in *to*.  A wrong password at ``POST /auth/login`` or
``POST /auth/reactivate`` and a wrong code at any two-factor endpoint each count
one failure.  The address is resolved as sign-in resolves it (``email__iexact``), so
every spelling the database matches to an account counts against that account; an
address no account holds is counted under the database's own ``UPPER()`` of it, the
comparison ``email__iexact`` makes, so no spelling of an address is counted apart
from the account it would sign in to, and the answers never say which addresses are
registered.  Once ``LOGIN_LOCKOUT_ATTEMPTS`` (10) failures fall within
``LOGIN_LOCKOUT_SECONDS`` (900) of the first, every attempt at that account, from
anywhere and with the right password too, is refused until that window has passed::

    429 {"detail": "Too many failed sign-in attempts for this email address. Try again later. Expected available in 812 seconds."}

with ``Retry-After`` in whole seconds.  Wrong codes are also counted over a day:
``LOGIN_LOCKOUT_CODE_ATTEMPTS`` (30) within ``LOGIN_LOCKOUT_CODE_SECONDS`` (86400)
lock the account out the same way, so somebody who holds the password cannot try
codes all day a few at a time.  A completed sign-in clears the fifteen-minute count
and leaves the day's.

The counts are rows of ``SignInFailureCount`` (:doc:`data-model`), keyed by SHA-256
digests so no address is stored.  They live in the database because the production
cache culls entries once it holds a few hundred, and a forgotten count would let
guesses through.  Each is updated under a row lock (``select_for_update``), so
concurrent failures are all counted; a row past its window reads as empty, and rows
whose window ended a day ago are deleted as failures are counted.

The failure that reaches a limit writes one WARNING line to the audit log, naming
the account when there is one and never the address::

    action=account.lockout actor=anonymous target=12 attempts=10 reason=too_many_failures

and mails the account (``sign_in_locked``), at most once a day.  Either setting of a
pair at ``0`` turns that count off (:ref:`configuration-login-lockout`).

**The trade-off.**  Anybody who knows an address can keep its sign-in paused by
guessing wrong every fifteen minutes, whoever owns it; that is the price of a limit
no spread of client addresses escapes.  The owner is mailed, and waits for the window
to pass, or asks a system administrator, who lifts the lockout at once with
``manage.py clear_lockout --email ADDRESS``; it forgets both counts and changes
nothing else.  ``reset_two_factor`` clears them too, and so does ``create_admin`` when
it takes an existing account back, along with the account's authenticator device and
backup codes.


How the portal uses this
========================

``src/portal/auth/useAuth.ts`` wraps the whole surface in TanStack Query hooks:
``useMe`` and ``useAuth`` for identity, ``useRoles`` for the catalog, and
``useLogin``, ``useReactivate``, ``useLoginMfa``, ``useLoginMfaEnroll``,
``useLoginMfaEnrollConfirm``, ``useRegister``, ``useLogout``, ``usePasswordChange``,
``usePasswordResetRequest``, ``usePasswordResetConfirm``, ``useEmailVerify``,
``useResendVerification``, ``useEmailChange``, and ``useEmailChangeUndo`` for the
mutations.  ``useRegister`` touches no cache, since nobody is signed in: the join
wizard's account step shows **Check your email** for every address.
``useEmailChange`` seeds ``['auth', 'me']`` with the answer, whose ``pending_email``
the Change email screen, the join wizard's verify step, and the member and user records
show as the change waiting; ``useEmailVerify`` invalidates it, so a signed-in member's
own payload says verified, or moved, straight away.  ``useEmailChangeUndo`` backs the
public ``/undo-email-change`` page and empties the cache, since every session of the
account has ended.  Login, reactivation, and logout all call ``queryClient.clear()`` so
no screen can show the previous user's data.  ``useLogin`` and ``useReactivate``
answer ``LoginResult``, the user or ``{"mfa": ...}`` (``isMfaChallenge`` tells
them apart), and only a user is put in the cache.  The sign-in page then shows the
second-factor step from ``features/two-factor/SignInSteps.tsx``: ``CodeStep``,
or ``EnrollStep``, which shows the QR code and the key, confirms a code, and shows
the backup codes (``RecoveryCodesPanel``, with **Copy** and **Download as .txt**)
before adopting the signed-in user (``useAdoptSignedIn``) once the person presses
**I saved these**.  A refusal carrying ``code: "mfa_expired"`` returns the page to
the password step with the server's sentence.  The profile's **Two-factor
sign-in** card (``features/two-factor/SecurityCard.tsx``) reads ``GET /auth/mfa``
through ``useMfaStatus`` in that feature's ``api.ts``, and the user record's
``TwoFactorCard`` posts the reset through ``useAccountStatusAction``.  The sign-in page reads a 403 whose
``code`` is ``deactivated`` as an offer: it shows a **Reactivate my account**
panel whose button sends the same credentials through ``useReactivate`` and then
continues as a sign-in would.  The profile page's **Deactivate my account** card
(``features/profile/DeactivateCard.tsx``) calls ``useDeactivate`` from the
profile feature's ``api.ts``, which clears the cache the same way, then goes to
``/login``.

``useSignOut`` wraps ``useLogout`` for the screens that sign somebody out: it
runs the mutation and, once the session is gone, navigates to ``/login``.  The
portal header's **Log out** control and the join wizard's **Use a different
account** control are both buttons that call it, so a session ends only when a
person presses one — no address signs anybody out by being opened.

``src/portal/auth/guards.tsx`` turns a missing session into a redirect to
``/login?next=<where they were going>`` and a missing role into the 403 page.
``RequireOnboarded``, nested inside ``RequireAuth`` around every signed-in route
except ``/change-email``, sends a reader who has not finished joining
(``isOnboarded`` in ``features/join/steps.ts``, true for a verified account with
``admin_created``) to ``/join/verify``,
``/join/profile``, or ``/join/pay``, whichever they still owe; the portal chrome
draws no rail for them (see :doc:`architecture`).
The guards wait for ``GET /auth/me`` to settle first, so a slow answer never
flashes the sign-in page at somebody who is in fact signed in.
``RequireOnboarded`` also waits while ``GET /auth/me`` is being refetched, since
the cached reader predates the change that set it off: a joiner whose payment
has just settled would otherwise be sent back to ``/join/pay``.

A check that fails outright is a third outcome, separate from both.  ``useMe``
takes the portal's retry policy, so a 5xx or a dropped connection is retried
twice before anything reacts to it; a 401 resolves to "nobody is signed in"
rather than an error, so signing out stays instant.  When the retries are
exhausted and nothing is cached, the guards render "We could not check your
sign-in" with a **Try again** button that asks ``GET /auth/me`` again, rather
than redirecting to the sign-in page.  A signed-in member whose background
refetch fails keeps the page they are on, because the cached answer is still
there.  The public screens -- the portal chrome, sign-in, and the join wizard
-- keep treating a failed check as anonymous, since each already renders
something usable for a visitor who is not signed in.

The users-admin screens live in ``src/portal/features/admin-users/``, with their
query hooks in ``api.ts``.  The user record's History card reads
``GET /admin/users/{id}/history`` through ``useAdminUserHistory``, whose key sits
under the users-admin key, so every save and status action reads it again.


Tests
=====

``backend/tests/test_accounts_auth.py``
   Registration (a new account, no second account for a taken address in either
   case, weak passwords, rollback), password change, the whole reset flow end to end
   through ``mail.outbox``, ``profile_complete``, and the throttles.

``backend/tests/test_registration.py``
   The one answer registration gives whoever holds the address, the session it never
   starts, refusals that read alike, and the message each kind of holder is mailed.

``backend/tests/test_email_change.py``
   A change of address: the request and what it leaves alone, the link to the new
   address and each way it is spent, an administrator's change, a donor's, and the
   undo link with each thing it does and each way it is refused.

``backend/tests/test_account_notices.py``
   The notice of a changed password, from a change and from a reset, and the mail
   sent after the answer (``send_after_response``).

``backend/tests/test_users_admin_api.py``
   The full role matrix on every users-admin endpoint, the search and filter
   parameters, and each business rule above.

``backend/tests/test_require_new_password.py``
   ``/require-new-password``: the role matrix, the unusable password, the deleted
   sessions, the old password refused at sign-in and at ``/auth/reactivate``, the
   email's wording and its link, an earlier link spent, a deactivated and a blocked
   account, each refusal, the audit lines and history entry, a mail server that
   refuses, and a password change or a stale edit racing the action.

``backend/tests/test_account_admin_passwords.py``
   The Django admin's accounts pages: no password on the change form, the add form
   and the change-password page closed, and a posted password changing nothing.

``backend/tests/test_user_history.py``
   Which changes write an ``AccountChange`` row and under whom, and the history
   endpoint's role matrix, order, and shape.

``backend/tests/test_admin_created_accounts.py``
   ``admin_created`` on accounts made on New member and by registration, the role
   descriptions' wording, and the refusal of a System administrator change.

``backend/tests/test_email_verification.py``
   The verification token and each way it is refused, the message, every path
   that sends one, and the verify, resend, and administrator resend endpoints.

``backend/tests/test_mail_failure_answers.py``
   Every request that sends mail, against a mail server that takes the message
   and one that refuses it: the same answer either way for the self-service and
   side-effect sends, the 503 on the two user-record sends, the failed email log
   row, the ``caldart.mail`` error record and the address it leaves out, a
   template that does not render answering 500 (or, for a reset sent after the
   answer, logged), and the error-mail handler that cannot raise.

``backend/tests/test_auth_api.py``
   The minimal surface the portal shell needs — CSRF, login, logout, me.

``backend/tests/test_verification_gate.py``
   The unverified-session gate: the 403 and its code on member endpoints, each
   allowed endpoint, no effect on a verified or anonymous caller or on the user
   guide, and the verification email's advice for an expired link.

``backend/tests/test_account_services.py``
   ``accounts.services`` on its own: creating an account, and each edit rule
   both allowed and refused, down to the field the refusal names.

``backend/tests/test_two_factor.py``
   ``apps.accounts.mfa`` on its own: who needs a second factor, enrolling, the
   authenticator code's window and replay, backup codes, turning it off, the reset,
   the pending sign-in, and that nothing secret is logged.

``backend/tests/test_two_factor_login.py``
   The password step's challenge, the code step, enrolling while signing in, and
   every way a pending sign-in is refused.

``backend/tests/test_two_factor_session.py``
   ``MfaSessionMiddleware``, the session mark, and the admin login routes'
   redirects, an unsafe ``next`` dropped.

``backend/tests/test_two_factor_self_service.py`` and ``test_two_factor_admin_reset.py``
   The ``/auth/mfa`` endpoints, and the user record's reset with its role matrix.

``backend/tests/test_login_lockout.py``
   The per-address lockout: its count, its window, the client address it ignores,
   unknown addresses, wrong codes, and its audit line.

``backend/tests/test_account_kinds.py``
   Members, friends, and donors: the effective kind in Python and SQL, the
   ``friend`` state, kind at registration and the donor upgrade, and every way a
   donor is kept from signing in.
