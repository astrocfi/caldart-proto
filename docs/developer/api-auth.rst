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
anonymous ones on this page: register, login, logout, the two password-reset
endpoints, and the email-verify endpoint all refuse a POST that carries no
token.  Call
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
  ``POST /auth/email/resend``, ``POST /auth/email/change``, and
  ``POST /auth/reactivate``.  A reset in particular must not tell the caller
  anything about the address, and any other answer would.
* A change an administrator saves that mails somebody along the way answers as
  it does when the message goes out too, because the change has committed: an
  edit of the address (``PATCH /admin/users/{id}``), a reactivation, and the
  member record's create, edit, and reactivation (:doc:`api-members`).
* A send the user administrator asks for by name,
  ``POST /admin/users/{id}/send-password-reset`` or
  ``POST /admin/users/{id}/send-email-verification``, answers **503** and
  records nothing in the audit log, so the administrator knows the message did
  not go:

  .. code-block:: json

     {"detail": "The mail server did not accept the message. A system administrator can see the attempt on the Sent Emails page."}

A refusal is ``caldart.mail.MailRefusedError``, which ``send_templated`` raises
only from an ``smtplib.SMTPException`` or an ``OSError`` (a connection refused, a
host that does not resolve, a TLS failure, a timeout) raised while the message is
handed to the mail server (:ref:`email-refused`).  Anything else, such as a
template that does not render, is a bug and answers 500.  The quiet answers go
through ``caldart.mail.send_logging_refusal``, or ``send_on_commit`` for a send
queued for the commit.


The user payload
================

Every endpoint that returns an account returns the same object:

.. code-block:: json

   {
     "id": 12,
     "email": "marta.reyes@example.org",
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
     "friend_on": null
   }

``roles``
   Slugs the account holds, always in privilege order (``member``,
   ``dart_leader``, ``user_admin``, ``account_admin``, ``website_admin``,
   ``system_admin``).  Roles are Django ``Group`` rows whose ``name`` is the
   slug, so adding a role later is a data change.

``membership``
   The membership summary from ``apps.members.services``.  ``status`` is one of
   ``current``, ``expired``, ``friend``, and ``donor``; an effective friend's is
   always ``friend``, with ``expires_on`` and ``plan`` null, and that includes a
   member who has never paid or been granted a term (see :ref:`kinds of account
   <account-kinds>`).  ``expires_on`` is
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
   account holds now: a verification link (see `Email verification`_), or a
   password reset or invitation link.  A new account and a changed address
   start false.  While it is false the API refuses the session everything but a
   few endpoints (see `Unverified sessions`_), and the portal shows only the join
   wizard's verify step.

``kind``
   ``member``, ``friend``, or ``donor``, as stored (:ref:`kinds of account <account-kinds>`):
   what the person asked to be.  A member with a pending ``friend_on`` still
   reads ``member`` here until the day comes; ``membership.status`` already
   reads ``friend`` from that day.  A member who registered and has not paid
   reads ``kind: "member"`` with ``membership.status: "friend"`` and
   ``friend_on: null``, and the portal reads the three to hold them at the join
   wizard's payment step.

``friend_on``
   The date a member who asked to become a friend becomes one, or ``null``.
   Read-only on every endpoint here.

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

Creates a member's or a friend's account, signs it in and returns the user
payload.  ``email``, ``password``, ``first_name``, and ``last_name`` are
required; ``kind`` is ``member`` (the default) or ``friend``, stored as given.
A member is an effective friend until a paid or granted term starts, so the
account reads ``membership.status: "friend"`` until the first payment clears.
In one transaction
the endpoint creates the ``User`` of that kind, grants the ``member`` role and
creates an empty ``MemberProfile``, then calls ``django.contrib.auth.login``.  If
any part fails, none of it is written.  No event is raised yet: the join
wizard asks for the DART at its profile step, and the ``PATCH /me/profile``
that completes the profile raises ``signed_up`` (:doc:`notification-events`).
Once the transaction commits, the new
address is mailed a verification link (see `Email verification`_), and the
payload's ``email_verified`` is false.

.. code-block:: json

   {"email": "marta.reyes@example.org", "password": "...",
    "first_name": "Marta", "last_name": "Reyes", "kind": "friend"}

.. code-block:: json

   {"id": 12, "email": "marta.reyes@example.org", "first_name": "Marta",
    "last_name": "Reyes", "roles": ["member"], "is_active": true,
    "membership": {"status": "friend", "expires_on": null, "plan": null,
                   "is_lifetime": false},
    "profile_complete": false, "email_verified": false, "kind": "friend",
    "friend_on": null}

**A donor's address upgrades the donor, once the address is proved.**  When the
address belongs to an active donor (:ref:`kinds of account <account-kinds>`), no
second account is made and nobody is signed in: the gifts on that account are
not shown to anyone who has not proved the address is theirs.  The donor's
account takes the password at once (a donor cannot sign in with it) and gets a
profile, and the address is mailed a verification link that carries the names
and the ``kind`` posted.  The answer is a 202 naming the address:

.. code-block:: json

   {"detail": "Verification message sent to giver@example.org."}

Following the link (`POST /auth/email/verify`_) completes the upgrade: the
account takes the names and the ``kind``, gains the ``member`` role, and is
verified, so the password chosen at registration then signs in.  Until then the
account is still a donor, and login answers it with the generic refusal.  The
donations already on the account stay on it, and the change of kind is audited
as ``account.kind``.  Registering again with the address mails a fresh link.

Rejections, all 400:

``{"email": ["This account has been closed. Contact CalDART to reopen it."]}``
   The address belongs to an account a user administrator has blocked from
   reactivating (:ref:`api-reactivation-block`).  The organization's name comes
   from the site settings.  No ``code``: the portal offers nothing further.

``{"email": ["This email belongs to a deactivated account. Sign in to reactivate it."], "code": "deactivated"}``
   The address belongs to any other deactivated account, of any kind.  ``code``
   lets the portal offer a sign-in instead of a second account.

``{"email": [...]}``
   The address is already in use by an active member or friend.  The check is
   case-insensitive, so ``A@example.org`` collides with ``a@example.org``.

``{"kind": [...]}``
   A kind other than ``member`` or ``friend``: nobody registers as a donor.

``{"password": [...]}``
   One of ``AUTH_PASSWORD_VALIDATORS`` refused it.  The validators run against
   the user-to-be, so a password that looks like the person's own name or email
   address is refused.

``{"<field>": ["This field is required."]}``
   A field was missing.  All four of the account's fields are mandatory.

Statuses: **201** with the user payload; **202** for a donor's address; **400**
for any rejection above; **429** when the ``auth_register`` throttle is
exhausted.  A refused verification message changes neither answer
(:ref:`refused sends <api-refused-send>`).

``POST /auth/login``
--------------------

Starts a session and returns the user payload.  Email matching is
case-insensitive (``UserManager.get_by_natural_key`` uses ``email__iexact``).

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
even one that somehow does is answered with the same 400 as wrong
credentials.

An account whose address is unverified signs in like any other and gets its
session, but that session reaches only the endpoints listed under `Unverified
sessions`_ until the address is verified.

Statuses: **200** with the user payload and a session cookie; **400** for a
missing field or wrong credentials; **403** for a deactivated or closed account
whose password was correct; **429** when the ``auth_login`` throttle is exhausted.

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
password.

* ``{"current_password": [...]}`` — did not match.
* ``{"new_password": [...]}`` — refused by a password validator.

Statuses: **204**; **400** for either rejection above or a missing field;
**401** when anonymous.

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
expired. Request a new one."]}``.  A weak new password is reported separately
under ``new_password``.

The endpoint does not sign the user in; the portal sends them to ``/login``.
The link could only have reached the owner of the address, so spending it also
marks an unverified address verified (``email_verified_at`` is set to now, and
an ``account.email_verified`` audit line is written); an address already
verified keeps its original time.  Either way, any bounce recorded against the
address is cleared.

A link for a deactivated account is accepted, and spending it reactivates the
account exactly as ``POST /auth/reactivate`` does — the person proved the address
and chose to come back — except that nobody is signed in: the portal sends them
to ``/login`` as for any reset.  A good link for an account a user administrator
has blocked from reactivating (one mailed before the block) is refused with
``{"token": ["This account has been closed. Contact CalDART to reopen it."]}``,
the organization's name read from the site settings, and no password is set.  The block is
read again from the locked account row, so one set while the reset is under way
refuses it the same way and rolls the whole reset back.

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
   otherwise ``is_active`` is cleared, ``account.deactivate`` is recorded with
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
* **400** ``{"detail": "A donor has no portal account to deactivate."}``, recorded
  with ``reason=donor_account``.  A donor cannot sign in, so this is a guard
  rather than a path anybody takes.

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
deactivated as well as one its owner deactivated.  The answer is the user
payload, as a sign-in gives it, with ``is_active`` true:

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
  with the body a failed sign-in gives.
* **403** ``{"detail": "This account has been closed. Contact CalDART to reopen
  it."}`` — the password matched, but a user administrator has blocked the
  account from reactivating (:ref:`api-reactivation-block`); it stays
  deactivated, and ``accounts.status.reactivate_own_account`` refuses it the same
  way, recorded as ``action=account.activate ... reason=reactivation_blocked``.

Statuses: **200** with the user payload and a session cookie, also when the mail
server refuses the verification link (:ref:`refused sends <api-refused-send>`);
**400** as above or for a missing field; **403** for a closed account; **429** when the ``auth_login`` throttle is exhausted.


Email verification
==================

A new account, a member an administrator creates with a password, and every
change of address are mailed a link that proves the address::

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

``accounts.services.update_account`` is the one hook for a change of address:
whenever an edit really changes ``email`` — compared stripped and
case-insensitively — it clears ``email_verified_at`` and mails the new address
once the transaction commits, with the address it replaced signed into the
link.  The same edit clears any bounce recorded against the old address
(``email_bounced_at`` and ``email_bounce_detail``).  That covers
``PATCH /admin/users/{id}``, ``PATCH /admin/members/{user_id}``, and
``POST /auth/email/change`` alike.  A mail server that refuses the link leaves
the edit standing and the answer unchanged
(:ref:`refused sends <api-refused-send>`).

``POST /auth/email/verify``
---------------------------

Follows a verification link.  Open to anonymous callers, because the mail
client may open the link in a browser that has no session.

.. code-block:: json

   {"token": "eyJ1c2VyIjoxMiwiZW1haWwiOiJtYXJ0YUBleGFtcGxlLm9yZyJ9:1xAG4w:..."}

.. code-block:: json

   {"email": "marta.reyes@example.org"}

The account the token names is stamped verified and an
``account.email_verified`` audit line is written; any bounce recorded against the
address is cleared, since mail to it has just arrived.  A link mailed when somebody
registered with a donor's address first upgrades the donor to the member or
friend that registration asked for (see `POST /auth/register`_); a donor's
link that carries no upgrade is refused like a forged one.  A link mailed after a
change of address carries the address it replaced, and the visit that stamps the
account verified raises the ``email_changed`` event with that old address
(:doc:`notification-events`).  Following a link a second
time answers 200 again and changes nothing.  Every way a link can be unusable —
a forged or mangled token, one older than the timeout, a deactivated or deleted
account, an address the account no longer holds — returns the same
``400 {"token": ["That verification link is invalid or has expired."]}``.

Statuses: **200**; **400** for an unusable token or a missing field; **429**
when the ``auth_verify`` throttle is exhausted.

``POST /auth/email/resend``
---------------------------

Mails the signed-in account's address a fresh verification link.  No body.

.. code-block:: json

   {"detail": "Verification message sent to marta.reyes@example.org."}

An address that is already verified is refused, and nothing is mailed::

    400 {"detail": "Your email address is already verified."}

Statuses: **202**, also when the mail server refuses the message
(:ref:`refused sends <api-refused-send>`); **400** for a verified address;
**401** when anonymous; **429** when the ``auth_verify_resend`` throttle is exhausted.

``POST /auth/email/change``
---------------------------

Moves the signed-in account to another address and returns the user payload,
whose ``email_verified`` is then false.  The address is the login, so the
current password is asked for first.

.. code-block:: json

   {"email": "marta@example.net", "current_password": "..."}

The checks run in this order and only the first failure is reported, each a
400 keyed on its field:

* ``{"current_password": ["That is not your current password."]}``
* ``{"email": ["That is already your email address."]}`` — compared
  case-insensitively.
* ``{"email": ["Another account already uses that email address."]}`` — also
  case-insensitive.

The change goes through ``accounts.services.change_own_email``, which is
``update_account`` with the account as both actor and target: it is audited as
``action=account.update actor=12 target=12 fields=email``, and the new address
is mailed a verification link on commit.  The session survives, so the caller
stays signed in.

Statuses: **200**, also when the mail server refuses the verification link
(:ref:`refused sends <api-refused-send>`); **400** for any rejection above or a
missing field; **401** when anonymous.


Unverified sessions
-------------------

A signed-in account whose ``email_verified`` is false may call only these:

* the endpoints an anonymous visitor may call: ``GET /auth/csrf``,
  ``POST /auth/login``, ``POST /auth/register``, ``POST /auth/password/reset``, and
  ``POST /auth/password/reset/confirm``;
* ``GET /auth/me`` and ``POST /auth/logout``;
* ``POST /auth/email/verify``, ``POST /auth/email/resend``, and
  ``POST /auth/email/change``;
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

All ten endpoints require the ``user_admin`` role.  ``system_admin`` passes
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
diagnostic, or ``""`` (:ref:`email-bounces`).

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
        "reactivation_blocked": false}
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

One user payload, exactly as the list returns it.

Statuses: **200**; **401** when anonymous; **403** without ``user_admin``;
**404** for an unknown id.

``PATCH /admin/users/{id}``
---------------------------

Accepts any of ``first_name``, ``last_name``, ``email``, and ``roles``, and
returns the updated payload.  ``PUT`` and ``DELETE`` are 405:
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
``friend_on``, ``is_active`` and ``reactivation_blocked`` are read-only here: an
``is_active`` sent in the body is ignored.  The kind is the account administrator's to change (:doc:`api-members`),
never the user administrator's, and the two flags change only through the
account status actions (:ref:`api-account-status`).  A write that really changes ``email``
clears ``email_verified_at`` and mails the new address a verification link (see
`Email verification`_), and clears any bounce recorded against the old address; a
change of capitalization alone leaves all of them alone.

A **Deleted member <id>** tombstone, which keeps a deleted account's payments,
takes no edit at all: the view refuses any body with **400** ``{"detail": "This
record keeps a deleted member's payments in the books and cannot be changed."}``
before the serializer runs, as the member record does
(:ref:`api-members-tombstone`).

Three rules are enforced in ``AdminUserSerializer``:

**Role slugs are validated.**  Anything outside ``ROLE_SLUGS`` is a 400 on
``roles``.  The list you send replaces the account's role groups exactly, and it
comes back sorted into privilege order.  Group memberships that are not roles —
Wagtail's editor groups, say — are left alone.  A list matching the groups the
account already holds is not a write: the groups and the Django flags are left
exactly as they are, so the portal may post the whole form on every save.

**Only a system administrator may move ``system_admin``.**  A write of the role
list moves it when the list ticks ``system_admin`` on an account whose groups
lack it, or leaves it unticked on an account that counts as a system
administrator.  From a caller who is not one, that is a 400 on ``roles``.  The
second half of the test reads *effective* roles, so a Django superuser without
the role group counts as a system administrator, and so does the caller who
holds the flag rather than the group.  A user administrator can therefore still
edit a system administrator's *other* roles, as long as ``system_admin`` stays
in the list — but no role list of a ``createsuperuser`` account is open to them,
because writing one rebuilds the flags from that list alone: leaving the role
out would take the superuser flag away, and putting it in grants the group.

**The account-edit guard covers ``email``.**  It is shared with ``PATCH
/admin/members/{user_id}`` and with the account status actions, and described in
full under :ref:`account-edit-guard` below.  ``first_name`` and ``last_name`` are outside
it: anyone who may open the record may correct a name on it.

Granting or revoking ``system_admin`` also syncs the Django flags, because a
system administrator is a Django superuser::

    user.is_superuser = "system_admin" in roles
    user.is_staff     = user.is_superuser or "website_admin" in roles

``website_admin`` is in that second line so an unrelated role edit cannot take
the Wagtail admin away from a website administrator.

Statuses: **200** with the updated payload; **400** for an unknown role slug,
a move of ``system_admin`` by a caller who is not one, an address already in
use, or a refusal from the account-edit guard below; **401** when anonymous;
**403** without ``user_admin``; **404** for an unknown id; **405** for ``PUT``
and ``DELETE``.

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
it on an active account should check the address on the member record.  A
donor, who cannot sign in, is refused with a sentence of its own::

    400 {"detail": "A donor cannot sign in, so no reset email was sent."}

Both the send and the refusal are recorded in the audit log
(:ref:`deploy-audit-log`).  A mail server that refuses the message is a 503
naming the Sent Emails page, and nothing is recorded in the audit log
(:ref:`refused sends <api-refused-send>`).

Statuses: **200** when the mail went out; **400** for an account that is
deactivated, holds no email address, or is a donor's; **401** when anonymous;
**403** without ``user_admin``; **404** for an unknown id; **503** when the mail
server refused the message.  This endpoint is not
throttled —
the throttles guard the anonymous routes.

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
server that refuses the message is a 503 naming the Sent Emails page, and
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
   (``accounts.status.deactivate_account``): ``is_active`` is cleared,
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
in, through ``POST /auth/reactivate``, by completing a password reset, or by
registering again with the address.  ``User.reactivation_blocked`` closes all four
doors.  Only a user administrator sets or clears it, through ``POST
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
* ``POST /auth/register`` refuses the address with the same sentence under
  ``email``;
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
Both administrator edit endpoints — ``PATCH /admin/users/{id}`` above and
``PATCH /admin/members/{user_id}`` in :doc:`api-members` — write through
``accounts.services.update_account``, which runs every write of ``email`` past
``accounts.services.check_account_edit`` first.  The status actions — the user
record's ``/deactivate``, ``/reactivate``, ``/block`` and ``/unblock`` above and
the member record's ``/deactivate`` and ``/reactivate`` — apply the same rule in
``accounts.status``.

The rule, in the order it is applied:

#. **Only a real change counts.**  An address that arrives carrying the value the
   account already has is not a change, so an administration form that resends
   every field is judged only on the fields it actually moves.  Email addresses
   are compared case-insensitively after stripping, exactly as the uniqueness
   constraint compares them.
#. **Nobody may deactivate or block their own account**, whatever roles they
   hold; ``POST /auth/deactivate`` (:ref:`api-deactivation`) is the one
   self-service path.
#. **Otherwise the actor must hold every role the target holds.**  A system
   administrator holds every role, so one always passes.

Both sides of that last comparison use *effective* roles:
``accounts.services.effective_roles`` adds ``system_admin`` whenever
``is_superuser`` is set.  An account created by ``manage.py createsuperuser``,
which sets the flag without adding the role group, is therefore protected — and
protects — like any other system administrator.

Worked through the roles: a user administrator may change a plain member's
address but not a DART leader's or an account administrator's, an account
administrator may not change a user administrator's, and a system administrator
may change anybody's.  Every role counts, administrative or not.  Names are
outside the guard entirely, so a user administrator can still correct the
spelling of a system administrator's surname.

What the guard measures is the write in front of it, against the roles the two
accounts hold when it arrives — it does not bound what the caller can reach over
two requests.  A user administrator may grant themselves the role they lack, or
take it off the target, and send the refused edit again; both are ordinary
``roles`` writes on ``PATCH /admin/users/{id}``, which is the role's whole
purpose.  ``system_admin`` is where the two rules meet and the reach stops: that
role is refused in both directions to a caller who is not a system
administrator, so a system administrator's account — a ``createsuperuser`` one
included — is closed to a lower administrator by either route.  Against an
account administrator the guard is absolute in one request as well as two,
because ``PATCH /admin/members/{user_id}`` has no ``roles`` field at all.

On a record whose address the caller may not write, a value that is not a real
change is dropped rather than saved, so an address resent in another case leaves
the stored one exactly as it was.  A caller who may write it saves what they
sent, case included.

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
A donor             A donor has no portal account to deactivate. (or *to
                    reactivate.*, or *to block.*)
A blocked account   A user administrator has blocked this account from
                    reactivating. Allow reactivation on its user record first.
No change           That account is already deactivated. (or *That account is
                    already active.*)
==================  ==============================================================

Every refusal but the last also writes one WARNING record to the audit log
(:ref:`deploy-audit-log`)::

    action=account.update actor=12 target=3 fields=email reason=roles_not_held

Account ids, field names and a reason slug only: no address, and nothing else
that identifies a person.  A refused role change reads
``action=account.roles ... reason=system_admin_role``; a refused status action
reads ``action=account.deactivate``, ``account.activate``, ``account.block`` or
``account.unblock`` with ``reason=self_deactivation``, ``roles_not_held``,
``donor_account`` or ``reactivation_blocked``.  An action that goes through is
recorded the same way at INFO, under the administrator.  The self-service
endpoints record ``action=account.deactivate actor=12 target=12
self_service=true`` and ``action=account.activate actor=12 target=12
self_service=true``.


Rate limiting
=============

Login, reactivation, registration, both password-reset endpoints, the
email-verify endpoint, the verification resend, and the public donation
checkout are throttled by client address.  The classes are in
``apps.accounts.throttling``; they subclass
``AnonRateThrottle`` but override ``get_cache_key`` so a session does not exempt
the caller — registration signs the new account in, so every request after the
first would otherwise carry a cookie and go uncounted.

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
``donate``               10/hour                    ``AUTH_THROTTLE_DONATE``
=======================  =========================  ===========================

``donate`` guards only ``POST /donations/checkout``: the calls that finish or
read a gift are proven instead by the signed token that checkout answers (see
:doc:`api-payments`), so throttling them by address would gain nothing.

A scope mapped to ``None`` — or missing from the dict — is inert.
``caldart/settings/test.py`` maps every scope to ``None`` so the suite never
races a shared counter; the throttling tests turn one back on with
``override_settings`` and clear the cache around themselves.

An exceeded throttle is DRF's usual **429** with a ``Retry-After`` header.


How the portal uses this
========================

``src/portal/auth/useAuth.ts`` wraps the whole surface in TanStack Query hooks:
``useMe`` and ``useAuth`` for identity, ``useRoles`` for the catalog, and
``useLogin``, ``useReactivate``, ``useRegister``, ``useLogout``, ``usePasswordChange``,
``usePasswordResetRequest``, ``usePasswordResetConfirm``, ``useEmailVerify``,
``useResendVerification``, and ``useEmailChange`` for the mutations.
``useEmailChange`` seeds ``['auth', 'me']`` with the answer, and
``useEmailVerify`` invalidates it, so a signed-in member's own payload says
verified straight away.
Login, reactivation, registration, and logout all call ``queryClient.clear()`` so
no screen can show the previous user's data.  The sign-in page reads a 403 whose
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
(``isOnboarded`` in ``features/join/steps.ts``) to ``/join/verify``,
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
query hooks in ``api.ts``.


Tests
=====

``backend/tests/test_accounts_auth.py``
   Registration (happy path, duplicate address in either case, weak passwords,
   rollback), password change, the whole reset flow end to end through
   ``mail.outbox``, ``profile_complete``, and the throttles.

``backend/tests/test_users_admin_api.py``
   The full role matrix on every users-admin endpoint, the search and filter
   parameters, and each business rule above.

``backend/tests/test_email_verification.py``
   The verification token and each way it is refused, the message, every path
   that sends one, and the verify, resend, change, and administrator resend
   endpoints.

``backend/tests/test_mail_failure_answers.py``
   Every request that sends mail, against a mail server that takes the message
   and one that refuses it: the same answer either way for the self-service and
   side-effect sends, the 503 on the two user-record sends, the failed email log
   row, the ``caldart.mail`` error record and the address it leaves out, a
   template that does not render answering 500, and the error-mail handler that
   cannot raise.

``backend/tests/test_auth_api.py``
   The minimal surface the portal shell needs — CSRF, login, logout, me.

``backend/tests/test_verification_gate.py``
   The unverified-session gate: the 403 and its code on member endpoints, each
   allowed endpoint, no effect on a verified or anonymous caller or on the user
   guide, and the verification email's advice for an expired link.

``backend/tests/test_account_services.py``
   ``accounts.services`` on its own: creating an account, and each edit rule
   both allowed and refused, down to the field the refusal names.

``backend/tests/test_account_kinds.py``
   Members, friends, and donors: the effective kind in Python and SQL, the
   ``friend`` state, kind at registration and the donor upgrade, the
   deactivated refusal, and every way a donor is kept from signing in.
