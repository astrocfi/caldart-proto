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
anonymous ones on this page: register, login, logout and the two
password-reset endpoints all refuse a POST that carries no token.  Call
``GET /api/v1/auth/csrf`` whenever you have no ``csrftoken`` cookie to echo;
the SPA's ``api/client.ts`` does this automatically before every POST, PUT,
PATCH or DELETE that finds the cookie missing.

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


The user payload
================

Every endpoint that returns an account returns the same object::

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
      "profile_complete": true
    }

``roles``
   Slugs the account holds, always in privilege order (``member``,
   ``dart_leader``, ``user_admin``, ``account_admin``, ``website_admin``,
   ``system_admin``).  Roles are Django ``Group`` rows whose ``name`` is the
   slug, so adding a role later is a data change.

``membership``
   The membership summary from ``apps.members.services``.  ``expires_on`` is
   the end of the member's *unbroken* coverage, so an early renewal shows next
   year's date immediately, and it is ``null`` for a lifetime membership.
   A single-user endpoint such as ``/auth/me`` calls ``membership_status``,
   which works it out in Python; ``GET /admin/users`` reads it from the SQL
   annotations its queryset carries, so the page costs the same number of
   queries whatever its size (see :ref:`membership-status-sql`).  Both state
   the same rule and give the same answer.

``profile_complete``
   True when the member profile has ``phone``, ``address_line1``, ``city``,
   ``postal_code`` and ``pilot_certificate_type`` filled in.  False when there is
   no profile at all.  The portal uses it to decide whether to nag.

The payload is read-only everywhere except ``PATCH /admin/users/{id}``.


Authentication
==============

``GET /auth/csrf``
------------------

204, and sets the ``csrftoken`` cookie.  Open to anyone.

``POST /auth/register``
-----------------------

Creates a member account, signs them in and returns **201** with the user
payload::

    POST /api/v1/auth/register
    {"email": "...", "password": "...", "first_name": "...", "last_name": "..."}

All four fields are required.  In one transaction the endpoint creates the
``User``, grants the ``member`` role and creates an empty ``MemberProfile``, then
calls ``django.contrib.auth.login``.  If any part fails, none of it is written.

Rejections, all 400:

``{"email": [...]}``
   The address is already in use.  The check is case-insensitive, so
   ``A@example.org`` collides with ``a@example.org``.

``{"password": [...]}``
   One of ``AUTH_PASSWORD_VALIDATORS`` refused it.  The validators run against
   the user-to-be, so a password that looks like the person's own name or email
   address is refused.

``{"<field>": ["This field is required."]}``
   A field was missing.  All four are mandatory.

``POST /auth/login``
--------------------

``{"email", "password"}`` → 200 with the user payload, and a session cookie.
Email matching is case-insensitive (``UserManager.get_by_natural_key`` uses
``email__iexact``).

* **400** ``{"detail": "Incorrect email address or password."}`` — wrong
  credentials.  The message never says which half was wrong.
* **403** ``{"detail": "This account has been deactivated. ..."}`` — the
  credentials may well be right, but ``is_active`` is false.

``POST /auth/logout``
---------------------

204.  Safe to call when nobody is signed in.

``GET /auth/me``
----------------

The signed-in user's payload, or **401** when anonymous.  This is the portal's
single source of truth for identity; the SPA caches it under the TanStack Query
key ``['auth', 'me']`` and everything that can change who you are writes or
invalidates that key.


Passwords
=========

``POST /auth/password/change``
------------------------------

``{"current_password", "new_password"}`` → **204**.  Requires a session.

The view calls ``update_session_auth_hash`` afterwards, so changing your
password does not sign you out of the browser you changed it from.  Other
sessions are invalidated, because the session auth hash is derived from the
password.

* ``{"current_password": [...]}`` — did not match.
* ``{"new_password": [...]}`` — refused by a password validator.

``POST /auth/password/reset``
-----------------------------

``{"email"}`` → **204, always**.  Whether the address is registered, belongs to a
deactivated account, or has never been seen, the answer is identical: the
endpoint must not be usable to enumerate members.  A malformed address is still
a 400, since that is a client bug rather than an answer about the database.

When there is an active account, ``apps.accounts.services.send_password_reset_email``
renders ``templates/emails/password_reset.{txt,html}`` and mails a link::

    {SITE_URL}/portal/reset-password?uid=<urlsafe_base64(pk)>&token=<token>

The token comes from ``django.contrib.auth.tokens.default_token_generator``, so
it is invalidated by the password changing or by ``PASSWORD_RESET_TIMEOUT``
(three days by default) elapsing.  In development Mailpit catches the mail on
SMTP 1025; read it at http://localhost:8025/.

``POST /auth/password/reset/confirm``
-------------------------------------

``{"uid", "token", "new_password"}`` → **204**.

Every way a link can be unusable — a mangled ``uid``, an unknown user, a
deactivated account, a token that has expired or has already been spent —
returns the same ``{"token": ["That password reset link is invalid or has
expired. Request a new one."]}``.  A weak new password is reported separately
under ``new_password``.

The endpoint does not sign the user in; the portal sends them to ``/login``.


Roles
=====

``GET /roles``
--------------

Any authenticated caller.  Returns the catalog, in privilege order::

    [{"slug": "member", "description": "Own profile, own payments and ..."}, ...]

Descriptions live in ``apps.accounts.roles.ROLE_DESCRIPTIONS``, which is also
what ``manage.py seed_roles`` iterates, so the API, the seed and the portal's
role checkboxes can never drift apart.


Users admin
===========

All four endpoints require the ``user_admin`` role.  ``system_admin`` passes
every role check, so system administrators have them too; every other role gets
403.

``GET /admin/users``
--------------------

Paginated list of user payloads, ordered by last name, first name, email.

=================  ============================================================
Parameter          Effect
=================  ============================================================
``search``         Case-insensitive match on first name, last name and email.
                   Terms are ANDed, so ``Ada Lovelace`` matches one person.
``role``           One role slug.  An unknown slug is a 400, not an empty page.
``is_active``      ``true`` / ``false``.
``ordering``       One of ``last_name``, ``first_name``, ``email``,
                   ``is_active``, ``created_at``; prefix with ``-`` to reverse.
                   Unlike ``role``, an unrecognized field is *ignored* rather
                   than rejected, so a typo silently gives you the default
                   order.
``page``,          Standard pagination.
``page_size``
=================  ============================================================

``GET /admin/users/{id}``
-------------------------

One user payload; 404 for an unknown id.

``PATCH /admin/users/{id}``
---------------------------

Accepts any of ``first_name``, ``last_name``, ``email``, ``is_active`` and
``roles``, and returns the updated payload.  ``PUT`` and ``DELETE`` are 405:
this API edits accounts, it does not replace or remove them.  Deleting a member
is ``DELETE /admin/members/{user_id}``, behind ``account_admin`` — see
:doc:`api-members`.

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

**The account-edit guard covers ``email`` and ``is_active``.**  It is shared
with ``PATCH /admin/members/{user_id}`` and described in full under
:ref:`account-edit-guard` below.  ``first_name`` and ``last_name`` are outside
it: anyone who may open the record may correct a name on it.

Granting or revoking ``system_admin`` also syncs the Django flags, because a
system administrator is a Django superuser::

    user.is_superuser = "system_admin" in roles
    user.is_staff     = user.is_superuser or "website_admin" in roles

``website_admin`` is in that second line so an unrelated role edit cannot take
the Wagtail admin away from a website administrator.

``POST /admin/users/{id}/send-password-reset``
----------------------------------------------

Sends the same email as ``/auth/password/reset``, but this one reports what
happened, because the caller is a trusted administrator rather than an anonymous
visitor::

    200 {"detail": "Password reset email sent to marta.reyes@example.org."}
    400 {"detail": "That account is deactivated, so no reset email was sent."}
    404 — no such account


.. _account-edit-guard:

The account-edit guard
======================

``email`` and ``is_active`` are the two account fields an administrator could use
to take an account over: the address is the login *and* where a password reset
link is mailed, and clearing the flag locks the account's owner out.  Both
administrator edit endpoints — ``PATCH /admin/users/{id}`` above and ``PATCH
/admin/members/{user_id}`` in :doc:`api-members` — run every write of those two
fields past ``accounts.services.check_account_edit`` first.

The rule, in the order it is applied:

#. **Only a real change counts.**  A field that arrives carrying the value the
   account already has is not a change, so an administration form that resends
   every field is judged only on the fields it actually moves.  Email addresses
   are compared case-insensitively after stripping, exactly as the uniqueness
   constraint compares them, and ``is_active`` as a boolean.
#. **Nobody may deactivate their own account**, whatever roles they hold.
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

On a record whose protected fields the caller may not write, a value that is not
a real change is dropped rather than saved, so an address resent in another case
leaves the stored one exactly as it was.  A caller who may write those fields
saves what they sent, case included.

A refusal is a 400 keyed on the field it belongs to, the same shape as the
``roles`` guard, so a client can show it against the input it came from::

    400 {"email": ["<message>"]}

=================  =============  ===============================================
Refused change     Field          Message
=================  =============  ===============================================
Your own status    ``is_active``  You cannot deactivate your own account.
Their address      ``email``      You cannot change the email address of an
                                  account that holds roles you do not hold.
Their status       ``is_active``  You cannot activate or deactivate an account
                                  that holds roles you do not hold.
=================  =============  ===============================================

When both fields are refused at once the complaint lands on ``email``.  Every
refusal also writes one WARNING record to the ``apps.accounts.services``
logger::

    Account edit refused: actor=12 target=3 fields=email

Account ids and field names only: no address, and nothing else that identifies a
person.


Rate limiting
=============

Login, registration and both password-reset endpoints are throttled by client
address.  The classes are in ``apps.accounts.throttling``; they subclass
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
=======================  =========================  ===========================

A scope mapped to ``None`` — or missing from the dict — is inert.
``caldart/settings/test.py`` maps every scope to ``None`` so the suite never
races a shared counter; the throttling tests turn one back on with
``override_settings`` and clear the cache around themselves.

An exceeded throttle is DRF's usual **429** with a ``Retry-After`` header.


How the portal uses this
========================

``src/portal/auth/useAuth.ts`` wraps the whole surface in TanStack Query hooks:
``useMe`` and ``useAuth`` for identity, ``useRoles`` for the catalog, and
``useLogin``, ``useRegister``, ``useLogout``, ``usePasswordChange``,
``usePasswordResetRequest`` and ``usePasswordResetConfirm`` for the mutations.
Login, registration and logout all call ``queryClient.clear()`` so no screen can
show the previous user's data.

``src/portal/auth/guards.tsx`` turns a missing session into a redirect to
``/login?next=<where they were going>`` and a missing role into the 403 page.
The guards wait for ``GET /auth/me`` to settle first, so a slow answer never
flashes the sign-in page at somebody who is in fact signed in.

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

``backend/tests/test_auth_api.py``
   The minimal surface the portal shell needs — CSRF, login, logout, me.
