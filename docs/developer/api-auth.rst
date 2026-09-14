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
``rest_framework.authentication.SessionAuthentication`` is the only
authentication class configured.

**CSRF.**  Every unsafe method needs an ``X-CSRFToken`` header.  Call
``GET /api/v1/auth/csrf`` once per page load to get the cookie; the SPA's
``api/client.ts`` does this automatically before the first POST, PUT, PATCH or
DELETE.

**401, not 403, for anonymous callers.**  Session authentication has no
``WWW-Authenticate`` challenge, so DRF would normally answer 403.
``caldart.exceptions.caldart_exception_handler`` rewrites that to 401, which is
what the contract promises and what the SPA keys "sign in again" off.  A 403
therefore always means *signed in, wrong role*.

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
   Straight from ``apps.members.services.membership_status``.  ``expires_on`` is
   the end of the member's *unbroken* coverage, so an early renewal shows next
   year's date immediately, and it is ``null`` for a lifetime membership.

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
Wagtail's editor groups, say — are left alone.

**Only a system administrator may move ``system_admin``.**  Formally: if
``system_admin`` appears in the symmetric difference between the roles you sent
and the roles the account already holds, and you are not a system administrator,
the request is 400.  A user administrator can therefore still edit a system
administrator's *other* roles, as long as ``system_admin`` stays in the list.

**Nobody may deactivate themselves.**  ``is_active: false`` on your own record is
a 400 on ``is_active``.  Sending ``is_active: true`` for yourself is a harmless
no-op.

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
