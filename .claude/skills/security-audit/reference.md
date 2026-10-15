# Security audit: reference

Example findings and common false positives. Paths and names are illustrative.

## Example findings

#### SEC-001: Any signed-in user can read any other user's profile
**P0** · Confirmed · Effort S
- **Where:** `api/views/profiles.py:58` (`ProfileDetail.get_object`)
- **Issue:** The detail view looks the profile up by the id in the URL and checks only that
  the caller is authenticated; the list view scopes to the caller, the detail view does not.
- **Impact:** Any member can walk sequential ids and read every member's address, phone,
  and date of birth.
- **Fix:** Scope the queryset to the caller (or to roles allowed to see others) and return
  404 for objects outside it; add a test per role.
- **Standard:** OWASP API1:2023 (broken object level authorization).

#### SEC-002: Password reset link built from the request's Host header
**P1** · Confirmed · Effort S
- **Where:** `accounts/services.py:112`
- **Issue:** The reset email's link uses `request.build_absolute_uri()`, so its host is
  whatever the requester sent.
- **Impact:** An attacker requests a reset for a victim with `Host: evil.example`; a victim
  who clicks the emailed link hands the token to the attacker, who takes over the account.
- **Fix:** Build the link from the configured site URL; restrict accepted hosts.

#### SEC-003: No MFA for administrators or billing staff
**P1** · Confirmed · Effort L
- **Where:** authentication settings (`settings/base.py:88`); no MFA package or model.
- **Issue:** Accounts that can grant roles, export every member's data, and issue refunds
  are protected by a password alone.
- **Impact:** One phished or reused password gives full control of member data and money.
- **Fix:** Add TOTP MFA (with recovery codes) required for the privileged roles, enforced on
  every login path including the admin site.

#### SEC-004: Webhook accepted before its signature is checked
**P1** · Likely · Effort S
- **Where:** `payments/webhooks.py:40-61`
- **Issue:** The handler parses the payload and marks the payment paid, then verifies the
  signature in a `try` whose `except` logs and returns 200.
- **Impact:** Anyone who can reach the endpoint can mark any payment as paid.
- **Fix:** Verify the signature over the raw body first and return 400 on failure; make the
  handler idempotent on the event id.

#### SEC-005: Member export writes cells that a spreadsheet will execute
**P2** · Confirmed · Effort S
- **Where:** `reports/csv.py:27`
- **Issue:** Free-text fields go into the CSV unchanged.
- **Impact:** A member who sets their name to `=HYPERLINK(...)` gets a formula run on the
  administrator's machine when the export is opened.
- **Fix:** Prefix cells starting with `=`, `+`, `-`, `@`, tab, or carriage return with `'`.

#### SEC-006: Login endpoint doesn't throttle attempts
**P1** · Confirmed · Effort S
- **Where:** `accounts/api/views.py:30`; no throttle classes in settings.
- **Issue:** Unlimited password attempts per account and per address.
- **Impact:** Credential stuffing and online guessing at full speed.
- **Fix:** Throttle by account and by client IP, with a delay or lockout that a third party
  cannot use to lock the victim out indefinitely.

#### SEC-007: Error reports include request bodies
**P2** · Confirmed · Effort S
- **Where:** `settings/prod.py:140` (error reporter `send_default_pii=True`)
- **Issue:** Error events carry request bodies, including passwords on the login endpoint.
- **Impact:** Anyone with access to the error-reporting service can read credentials.
- **Fix:** Disable default PII and scrub authentication fields before sending.

#### SEC-008: Third-party action pinned to a moving tag
**P3** · Confirmed · Effort S
- **Where:** `.github/workflows/ci.yml:31`
- **Issue:** `uses: some-org/some-action@v2`; the tag can be repointed.
- **Impact:** A compromised action runs with the workflow's token and secrets.
- **Fix:** Pin to a commit SHA with a comment naming the version; set `permissions:` to the
  minimum.

## Common false positives

Check these before reporting:

- **`csrf_exempt` on a webhook** whose signature is verified first: legitimate. Report only
  if the signature check is missing, skippable, or after side effects.
- **`mark_safe` or `dangerouslySetInnerHTML` on constants**, on output of a maintained
  sanitizer, or on content only administrators write and only administrators see: not XSS.
  Content an editor writes that the public sees is still worth checking.
- **`subprocess` with a list argv** built from settings or constants: not command
  injection. Check the arguments' origin.
- **`random` for non-security purposes** (jitter, sampling, demo data): not a finding.
- **Secrets in test settings, fixtures, and `.env.example`** that are obviously fake and
  cannot be used against any real system: not a leak. A value that looks real is a finding
  until shown otherwise.
- **ORM `raw` or `extra` with parameters passed separately**: not SQL injection; with
  string formatting of input: injection.
- **`AllowAny` on login, registration, password reset, public content, and health
  checks**: expected. Report only what those endpoints return or do.
- **MD5 or SHA-1 for cache keys, ETags, or file fingerprints**: not a cryptographic use.
- **A 404 instead of 403** for objects outside the caller's scope: the correct choice, not
  an inconsistency.
- **A missing header the web server adds**: check the deployment configuration before
  reporting that the application does not set it.
