# Security audit checklist

The categories below are the report's sections, in order. Every reviewer applies every
category that its files touch. Each item is a question to answer from the code, not a box
to check off: a finding needs a location, an attacker, and a consequence.

The tags say where a check usually lands: **[B]** backend, **[F]** frontend, **[I]** the
interface between them (the HTTP contract, cookies, headers, and what each side trusts the
other to do), **[O]** operations (configuration, deployment, CI, repository).

When the repository documents an expectation (a permission matrix, a data-handling rule, a
security standard), check the code against the document and the document against good
practice. A gap in either direction is a finding.

## 1. Authentication

- **[B]** Passwords are hashed with a slow, salted, current algorithm (Argon2id, scrypt,
  bcrypt, or PBKDF2 with a current work factor). No reversible encryption, no plain hashes,
  no custom schemes. Hashes upgrade on login when the algorithm changes.
- **[B]** Password policy: minimum length (at least 8, preferably 12+), a breached or common
  password check, no maximum below 64, no composition rules that weaken entropy, no silent
  truncation.
- **[B]** Login resists brute force and credential stuffing: per-account and per-IP
  throttling or lockout, with lockout that cannot be used to lock out a victim
  indefinitely.
- **[B][I]** No account enumeration: login, registration, password reset, email change, and
  invitation answer identically (status, body, and timing) for existing and unknown
  accounts.
- **[B]** Password reset: tokens are random, single-use, short-lived, bound to the account
  and to the current password hash, stored hashed or signed, and invalidated by a password
  change. The reset link's host comes from configuration, never from the request's `Host`
  header. A reset logs out other sessions.
- **[B]** Email verification and invitation tokens follow the same rules; an unverified
  account cannot act as verified.
- **[B]** Changing a password, email address, or MFA setting requires the current password
  or a recent re-authentication, and notifies the old address.
- **[B]** Every login path is accounted for: the main login, admin or CMS login, API token
  issue, OAuth/OIDC/SAML callbacks, "magic link" login, impersonation, management or
  debug back doors. Each one enforces the same rules (throttling, MFA, account state).
- **[B]** Deactivated, deleted, or unverified accounts cannot authenticate by any path,
  including existing sessions and long-lived tokens.
- **[B]** OAuth/OIDC/SAML: `state` and PKCE checked, `redirect_uri` exactly matched, ID
  token signature, `aud`, `iss`, `exp`, and `nonce` validated, account linking by verified
  email only.
- **[B][I]** API tokens and JWTs: strong signing keys, an explicit algorithm allowlist (no
  `none`, no key confusion), expiry, revocation, scoped permissions, and no token in a URL.
- **[B]** Default, demo, or seed accounts and passwords cannot exist in production, or are
  forced to change.

## 2. Multi-factor authentication

- **[B]** Is MFA available? Is it required for privileged roles (administrators, anyone who
  can move money, export personal data, or change other users' roles)? Its absence for
  such roles is at least a P1 finding.
- **[B]** MFA cannot be bypassed by an alternate path: the admin or CMS login, the API, the
  password-reset flow (reset must not log the user in past MFA), "remember this device",
  social login, or a session created before MFA was enrolled.
- **[B]** TOTP codes are checked with a narrow window and cannot be replayed; codes are
  throttled. SMS is not the only factor for privileged roles.
- **[B]** Recovery codes are random, hashed at rest, single-use, and regenerated on demand.
- **[B]** Enrolling, disabling, or resetting MFA requires re-authentication, notifies the
  user, and an administrator's reset of another user's MFA is logged.
- **[B]** Sensitive actions (role grants, payouts or refunds, bulk export, changing payment
  configuration) ask for step-up authentication where the risk warrants it.

## 3. Session management

- **[B][I]** Session cookies are `Secure`, `HttpOnly`, and `SameSite=Lax` or `Strict`, with
  a `__Host-` prefix where possible; the session id rotates on login and privilege change
  (no fixation).
- **[B]** Idle and absolute timeouts exist and fit the data's sensitivity; logout destroys
  the server-side session, not only the cookie.
- **[B]** Password change, role change, deactivation, and MFA reset invalidate the user's
  other sessions and tokens.
- **[F]** Tokens are not kept in `localStorage` or `sessionStorage` where an XSS could read
  them; nothing sensitive is cached in the browser after logout (service workers, caches,
  persisted state).

## 4. Authorization and access control

- **[B]** Every route, view, API endpoint, GraphQL resolver, RPC method, admin action,
  websocket handler, and server-rendered page has an explicit authentication and
  authorization decision. Default-allow configuration, a missing permission class, or a
  permission declared on the class but overridden per method is a finding.
- **[B]** Object-level checks: a user cannot read, change, or delete another user's object
  by changing an id in the path, query, or body (IDOR/BOLA). List endpoints scope their
  querysets; detail endpoints do not rely on the list's scoping.
- **[B]** Field-level checks: a user cannot write fields they should not (role, owner,
  status, price, verified flags, foreign keys to other tenants) through mass assignment,
  nested writes, PATCH, or bulk endpoints. Read-only fields are enforced on the server.
- **[B]** Vertical escalation: a role cannot grant itself or others a higher role, edit a
  more privileged user, or reach an administrator action through a lower-privilege
  endpoint. The last administrator cannot be removed by accident or by a lesser role.
- **[B]** Function-level checks on exports, reports, bulk actions, search, autocomplete,
  previews, and download endpoints, which often skip the checks the main views have.
- **[I][F]** The frontend hides what a role cannot do, but the backend enforces it; a route
  guard, a hidden button, or a disabled field is never the only control.
- **[B]** Multi-tenant or group scoping (organizations, chapters, teams) is applied in every
  query, including joins, aggregates, and reports.
- **[B]** Admin, CMS, debug, health, metrics, and documentation endpoints are restricted to
  the people who need them.
- **[B]** Authorization decisions use server-side state, never a role, user id, or price the
  client sends.

## 5. CSRF and cross-origin controls

- **[B][I]** Every state-changing request authenticated by a cookie is protected by a CSRF
  token, an origin check, or a `SameSite=Strict` cookie. List each CSRF exemption and
  justify it (signature-verified webhooks are the usual legitimate case).
- **[B]** No state change on `GET` or `HEAD`; a GET that changes state bypasses CSRF and
  can be triggered by an image tag.
- **[B][I]** CORS: no wildcard origin with credentials, no reflected `Origin`, no `null`
  origin, no regular expression that matches attacker domains. Preflight is not the only
  defense for non-simple requests.
- **[B][I]** Clickjacking: `frame-ancestors` in CSP or `X-Frame-Options` on every page that
  takes an action.
- **[F]** `postMessage` handlers check `event.origin`; `window.opener` is cut for links that
  open in a new tab (`rel="noopener"`).
- **[B]** Login CSRF is prevented (the login form carries a token).

## 6. Injection

Trace every source of external input (request path, query, body, headers, cookies, uploaded
file names and contents, webhook payloads, email bodies, third-party API responses, database
contents written by other users, environment) to every sink below.

- **[B]** SQL: no string-built queries, no `raw`/`extra`/`execute` with interpolated input,
  no user-controlled `ORDER BY`, column, or table names without an allowlist. ORMs' raw
  escape hatches are checked one by one.
- **[B]** NoSQL, LDAP, XPath, and search-engine queries built from input.
- **[B]** OS commands: no `shell=True`, `os.system`, backticks, or `exec` with input;
  arguments passed as a list; no user-controlled program path or option injection (a value
  that starts with `-`).
- **[B]** Code execution: no `eval`, `exec`, `Function()`, dynamic `import`, or template
  compilation of user input; no unsafe deserialization (`pickle`, `yaml.load`,
  `marshal`, Java/PHP/.NET object deserialization, `node-serialize`).
- **[B]** Server-side template injection: user input is never the template, only its data.
- **[B]** Header and CRLF injection in redirects, `Content-Disposition` filenames, cookies,
  and email headers (To, Cc, Subject, Reply-To).
- **[B]** Path traversal: user input never reaches a filesystem path without normalization
  and a check that the result stays inside the expected directory; archive extraction
  checks each member (zip slip).
- **[B]** XML: external entities and DTDs disabled (XXE); no billion-laughs expansion.
- **[B]** CSV and spreadsheet exports neutralize cells starting with `=`, `+`, `-`, `@`, tab,
  or carriage return (formula injection).
- **[B]** Regular expressions built from input are escaped; prototype pollution through
  deep merge of request bodies (JavaScript backends).
- **[B]** Log injection: user input written to logs cannot forge lines (newlines escaped).

## 7. Cross-site scripting and client-side security

- **[F]** Every raw-HTML sink is listed and justified: `dangerouslySetInnerHTML`,
  `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `v-html`, `{@html}`,
  `[innerHTML]`, jQuery `.html()`. Each one is fed only by sanitized content (a maintained
  sanitizer with an allowlist) or by trusted constants.
- **[B]** Server templates: autoescaping on; every `|safe`, `mark_safe`, `{% autoescape off
  %}`, `Markup()`, `raw`, `html_safe`, or unescaped interpolation (`<%-`, `{{{ }}}`,
  `!=`) is checked for user-controlled data. Rich text from a CMS or editor is sanitized on
  save or render.
- **[F][B]** URLs built from data reject `javascript:`, `data:`, and `vbscript:` schemes
  (`href`, `src`, `formaction`, `window.location`, redirects).
- **[B][F]** Open redirects: `next`, `return_to`, `redirect` and similar parameters accept
  only relative paths or an allowlist of hosts, on both the server and the client.
- **[B][I]** Content Security Policy: present, without `unsafe-inline` or `unsafe-eval` for
  scripts where avoidable, with `object-src 'none'`, `base-uri`, and `frame-ancestors`.
- **[F]** JSON embedded in HTML is escaped against `</script>` breakout.
- **[F]** Third-party scripts and stylesheets are pinned with Subresource Integrity or
  self-hosted; the list of third parties that can run code in the page is known.
- **[F]** Production builds do not ship source maps, debug panels, mock servers, feature
  flags that unlock admin features, or secrets baked in at build time (every
  `VITE_*`, `NEXT_PUBLIC_*`, `REACT_APP_*` value is public).
- **[F]** Markdown, SVG, and user-uploaded HTML are rendered safely (sanitized, or served
  from a separate origin with `Content-Disposition: attachment`).

## 8. Data protection and privacy

Start from an inventory of the personal and sensitive data the system holds (names,
addresses, email, phone, dates of birth, medical or licensing data, payment data,
government ids, location, free-text notes) and of who is meant to see each item.

- **[B][I]** API responses return only the fields the caller's role needs. Serializers that
  return a whole model, a nested related object with more than the caller should see, or a
  field the UI never displays are findings. Compare what the API sends to what the
  frontend uses.
- **[B]** Personal data does not leak through side channels: search and autocomplete,
  error messages, counts, exports, emails, notifications, report subscriptions, admin
  list pages, public pages, sitemaps, caches, and URLs (which reach logs and `Referer`).
- **[B]** Emails go only to the intended recipients: bulk mail uses BCC or per-recipient
  sends, never exposes the recipient list, and checks each recipient's consent and status.
- **[B]** Deletion and deactivation actually remove or anonymize the data everywhere it is
  copied (logs, exports, backups policy, search indexes, third parties), and the retention
  of what remains is intentional.
- **[B][O]** Data at rest: database and backups encrypted or access-controlled; backups are
  not written into web-served or world-readable locations; database dumps and fixtures in
  the repository contain no real personal data.
- **[B]** Payment card data never touches the server unless the system is meant to be in
  PCI scope; tokens from the payment provider are used instead.
- **[I]** Responses with personal data are not cacheable by shared caches
  (`Cache-Control: no-store` or `private`).

## 9. Logging, monitoring, and error handling

- **[B]** Logs, error reports (Sentry and similar), analytics, and audit trails never contain
  passwords, tokens, session ids, API keys, full card numbers, reset links, or request
  bodies of authentication endpoints, and minimize personal data. Check the logging
  configuration, every log call that formats a request, user, or payload, and the error
  reporter's scrubbing settings.
- **[B][I]** Users never see stack traces, SQL, file paths, framework debug pages, or
  internal hostnames; production error handlers return generic messages with a
  correlation id.
- **[B]** Security events are logged with who, what, when, and from where: logins and
  failures, MFA changes, password resets, role and permission changes, exports, payment
  configuration changes, administrator actions on other users.
- **[B]** Audit logs cannot be altered or deleted by the users they record.
- **[O]** Somebody is alerted to repeated failures, error spikes, and failed background
  jobs.
- **[B]** Exceptions are not swallowed in security paths (a `try` around a signature check
  that falls through to success).

## 10. Secrets and cryptography

- **[O]** No secrets in the repository or its history: keys, passwords, tokens, connection
  strings, private certificates, `.env` files. Example and test values are obviously fake.
  A secret ever committed must be rotated; removing it from `HEAD` is not enough.
- **[B]** Secrets are read from the environment or a secret manager; the application fails
  to start in production when a required secret is missing or still the development
  default.
- **[B]** Random values for tokens, ids, passwords, and nonces come from a CSPRNG
  (`secrets`, `crypto.randomBytes`, `crypto.getRandomValues`), not `random` or
  `Math.random`.
- **[B]** No custom cryptography; current algorithms and modes (AES-GCM, ChaCha20-Poly1305,
  HMAC-SHA-256, Ed25519); no MD5 or SHA-1 for security; no ECB; no static IVs or nonces.
- **[B]** Secret comparisons use constant-time functions (`hmac.compare_digest`,
  `crypto.timingSafeEqual`).
- **[B]** TLS verification is never disabled for outbound calls (`verify=False`,
  `rejectUnauthorized: false`, `InsecureSkipVerify`).
- **[B]** Signed values (cookies, tokens, URLs) have a purpose or salt so one cannot be
  replayed as another, and an expiry.

## 11. Denial of service and resource limits

- **[B]** Rate limits on authentication, password reset, registration, contact and
  invitation forms, anything that sends email or SMS (cost and reputation abuse), search,
  and expensive reports or exports.
- **[B]** Every list endpoint paginates with a server-enforced maximum page size; no
  endpoint returns an unbounded queryset.
- **[B][O]** Request body, upload, and form-field limits are set at the web server and the
  application; JSON nesting depth, multipart part count, and query-string length are
  bounded.
- **[B]** Expensive work (PDF and CSV generation, image processing, bulk email, imports)
  runs with limits or in a background queue, not unbounded in the request.
- **[B]** Regular expressions applied to input have no catastrophic backtracking (ReDoS);
  decompression and image parsing have size limits (zip and pixel bombs).
- **[B]** Outbound HTTP calls have connect and read timeouts; retries are bounded with
  backoff.
- **[B]** N+1 queries or quadratic algorithms an attacker can trigger with large input.
- **[O]** Worker counts, timeouts, and database connection limits leave headroom; one slow
  endpoint cannot exhaust every worker.

## 12. Back channels and integrations

- **[B]** Webhooks: signature verified with the provider's library or a constant-time
  HMAC over the raw body, before any parsing that acts on the payload; timestamp tolerance
  against replay; idempotency on the event id; the handler re-fetches the object from the
  provider rather than trusting payload amounts where the provider recommends it.
- **[B]** SSRF: any URL or host the user can influence (link previews, webhooks the user
  registers, image fetch, imports, address or registry lookups) is checked against an
  allowlist or blocks private, loopback, link-local, and metadata addresses after DNS
  resolution and on every redirect.
- **[B]** Outbound email: links in emails use the configured site URL; templates escape
  user content; sender domains have SPF, DKIM, and DMARC where the repository configures
  them; bounce and complaint handling is authenticated.
- **[B]** Background jobs, scheduled tasks, and queues: job arguments are not trusted as if
  they came from the code; jobs re-check authorization for the user they act for; failed
  jobs do not retry forever.
- **[B][O]** Management commands, CLIs, and operator scripts: inputs validated, no shell
  injection, no secrets on the command line (visible in `ps`), destructive commands
  confirmed.
- **[B]** Service-to-service calls authenticate both ways; internal endpoints are not
  reachable from the internet; third-party responses are validated before use.
- **[B]** Third-party API keys are scoped to the least privilege the integration needs.

## 13. File handling

- **[B]** Uploads: size limit, allowlisted types checked by content (not only by extension
  or the client's `Content-Type`), a server-generated name, storage outside the web root
  or on a separate origin, and `Content-Disposition` and `X-Content-Type-Options: nosniff`
  when served.
- **[B]** Users can download only the files they are authorized for; file URLs are not
  guessable when access is restricted, or are checked on each request.
- **[B]** Images are re-encoded or stripped of metadata (EXIF location) when that matters.
- **[B]** Temporary files are created securely (`mkstemp`, not predictable names) and
  removed.

## 14. Business logic and race conditions

- **[B]** Prices, totals, discounts, fees, and refund amounts are computed on the server;
  the client's amount is never trusted; negative, zero, and fractional quantities are
  rejected.
- **[B]** Payment confirmation comes from the provider (webhook or server-side fetch), not
  from the browser's return URL.
- **[B]** State machines (membership, order, approval, verification) refuse invalid
  transitions; a step cannot be skipped by calling a later endpoint directly.
- **[B]** Race conditions: double-submit, double-refund, double-redeem, and
  check-then-act sequences use transactions, row locks, unique constraints, or idempotency
  keys.
- **[B]** Limits that matter (one vote, one free trial, one invitation use) are enforced by
  the database, not only by a prior read.

## 15. API and frontend-backend interface

- **[I]** Inventory every endpoint the backend exposes and every call the frontend makes.
  Endpoints the frontend never calls still need protection; calls the frontend makes to
  endpoints that do not exist hint at stale routes.
- **[I]** Validation happens on the server for every field the client can send; client-side
  validation is convenience only.
- **[I]** Error responses are consistent and do not distinguish "not found" from
  "forbidden" where that leaks existence.
- **[I]** Identifiers: sequential ids in URLs for sensitive objects make IDOR and
  enumeration cheap; consider them alongside the object-level checks.
- **[I]** HTTP methods: unexpected methods are rejected; `OPTIONS` and `TRACE` reveal
  nothing; method override headers are not honored.
- **[I]** API schema, GraphQL introspection, and interactive docs are not public unless
  intended; GraphQL has depth and cost limits.
- **[I]** The API sets `Content-Type: application/json` and the frontend never evaluates a
  response as script.

## 16. Configuration and deployment

- **[O]** Production settings: debug off, allowed hosts set, secure cookie flags,
  HTTPS redirect, HSTS (with `includeSubDomains` when appropriate), a proxy-aware scheme
  header that only a trusted proxy can set, and a secret key that is not the development
  one.
- **[O]** Security headers: CSP, `X-Content-Type-Options`, `Referrer-Policy`,
  `Permissions-Policy`, `Cross-Origin-Opener-Policy`, frame protection.
- **[O]** Web server and reverse proxy: TLS versions and ciphers, request size and timeout
  limits, no directory listing, hidden files (`.git`, `.env`) not served, client IP taken
  from a trusted proxy header only.
- **[O]** Processes run as an unprivileged user with the least filesystem access;
  systemd units, containers, and scripts use hardening options where available; secrets
  files are readable only by the service.
- **[O]** The database, cache, mail catcher, and admin tools are not exposed publicly;
  development services (debug toolbars, mail catchers, mock payment providers) cannot be
  enabled in production by accident.
- **[O]** Install and upgrade scripts: no `curl | sh` of unpinned content, safe temporary
  files, correct file permissions, no secrets echoed to the terminal or logs.
- **[O]** Documentation does not instruct operators to do something insecure (disable TLS
  verification, open a database port, run as root, reuse the demo password).

## 17. Supply chain and CI/CD

- **[O]** Dependencies: known-vulnerable versions (run the auditors), abandoned packages,
  typosquat-looking names, packages pulled from unofficial registries or git URLs, lock
  files committed and used in CI (`npm ci`, `--frozen`/`--locked`).
- **[O]** Install-time scripts (`postinstall`, build hooks) from dependencies.
- **[O]** CI workflows: `pull_request_target` or `workflow_run` with a checkout of untrusted
  code; untrusted input (`github.event.*.title`, `body`, `head_ref`) interpolated into a
  `run:` script; secrets exposed to forks; `permissions:` not minimized; third-party
  actions not pinned (a commit SHA is strongest); self-hosted runners on public repos;
  artifacts or caches that carry secrets.
- **[O]** Branch protection and required checks are what the documentation says (only
  checkable with repository access; note it if not checkable).
- **[O]** Vendored code and generated files: provenance and version known; not modified in
  ways that hide changes.

## 18. Security testing

- **[B][F]** Tests exist for the controls above: permission denial per role and endpoint,
  object-level access, CSRF enforcement, rate limiting, webhook signature rejection, input
  validation, and the absence of sensitive fields in responses. A missing test for a
  control that has no finding is P3; a missing test for a control that is broken belongs
  with that finding.
- **[B]** Test settings or fixtures do not weaken production code paths (a test-only flag
  that disables a check and could be set in production).
- **[O]** Security scanners or audits run in CI.
