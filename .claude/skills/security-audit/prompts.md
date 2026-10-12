# Reviewer prompts

The orchestrator launches two kinds of reviewer subagents: **slice reviewers**, one per
slice in the ledger, which read every line of their files; and **cross-cutting reviewers**,
which follow one concern across the whole repository. Fill the placeholders (`<...>`) and
pass the prompt as written. Every reviewer is a general-purpose subagent with read and
search tools.

## Shared preamble

Begin every reviewer prompt with this block.

```text
You are one reviewer in a full security audit of the repository at <repo root>
(commit <short sha>). The audit is read-only: do not edit, create, or delete any file in
the repository, do not commit, do not push, do not open issues, do not send requests to
any deployed system, and do not start servers. You may run read-only commands (cat, grep,
git log, git show) and write scratch files only under <scratch dir>.

Read these first:
- The threat-model brief: <scratch dir>/brief.md
- The checklist: <skill dir>/checklist.md
- The search patterns, sections for <stacks>: <skill dir>/patterns.md
- The project's own security standards, if any: <list of rule or standards files, or "none">

Report only what you have confirmed by reading the code, or mark the confidence lower. A
pattern match alone is not a finding. Never copy a secret's value into your answer: give
its location, its kind, and at most its first four characters.

Priorities: P0 critical (exploitable now by an unauthenticated or low-privilege attacker
with severe impact), P1 high (exploitable with a realistic precondition and significant
impact, or a missing standard control such as MFA for administrators), P2 medium
(defense-in-depth gap or limited impact), P3 low (hardening), Info (observation, no action
needed). Propose a priority; the orchestrator assigns the final one.
```

## Slice reviewer

```text
<shared preamble>

Your assignment is slice <slice id> (<class>): the files listed below, <n> files,
<lines> lines. Read every file in full, line by line, using offsets for files longer than
your read limit. Do not sample.

<one path per line>

Apply every checklist category that these files touch. For each file, ask what external
input reaches it, what it trusts, what it exposes, and what it would take to abuse it.
When a concern depends on code outside your slice (a permission checked elsewhere, a
helper's escaping), open that code to confirm it rather than guessing, and say what you
checked.

<one of the class notes below>

Return exactly the format in "Reviewer output" below.
```

Class notes, chosen by the slice's class:

- **code:** "These are application source and configuration files. Apply the full
  checklist."
- **test:** "These are test files. Look for real secrets or personal data in fixtures,
  test-only switches that weaken production code paths, tests that assert insecure
  behavior as correct, and controls that the tests show are untested (checklist category
  18). Read every file, but you do not need to apply the production-code checks to test
  helpers."
- **prose:** "These are documentation and text files. Grep every file for the secret and
  personal-data patterns, read in full every page about installation, deployment,
  configuration, operations, authentication, permissions, or security, and skim the rest.
  Look for leaked secrets, real personal data, internal hostnames or addresses, insecure
  operating instructions, and documented security behavior (permission matrices, data
  rules) the code reviewers must check against. In your files list, mark each file `read`
  or `scanned`."

## Cross-cutting reviewers

Each one follows its concern across the whole repository, using the ledger
(`<scratch dir>/ledger.json`) to find the relevant files, and reads them in full. Launch all
of them unless the brief shows a concern cannot apply (for example, no webhooks and no
outbound calls), and say in the report which were skipped and why.

```text
<shared preamble>

Your assignment is the cross-cutting concern "<name>": checklist categories <numbers>.
<the concern's method, from the table below>

Return exactly the format in "Reviewer output" below. In the files list, name the files you
read in full.
```

| Name | Categories | Method |
| --- | --- | --- |
| Identity | 1, 2, 3 | Find every way a principal is established: each login form and endpoint, admin or CMS login, token issue, SSO callback, magic link, impersonation, invitation, password reset, email verification, and any management command that creates or elevates a user. Trace each path from request to session or token, and check each one against categories 1 to 3. State plainly whether MFA exists and for whom. |
| Access control | 4, 15 | Build the endpoint inventory: every route the backend serves (URL configuration, routers, decorators, admin, CMS, static and media serving, health and debug routes), with its methods, authentication, permission checks, and object scoping. Compare it to the documented permission matrix if there is one. Then list the frontend's route guards and API calls and compare them to the backend. Report the inventory as a compact table in your scratch directory (`<scratch dir>/endpoints.md`) and the findings in your answer. |
| Interface and browser | 5, 7, 15 | Follow a request from the browser to the server and back: cookies and their flags, CSRF token handling on both sides, CORS, security headers and CSP as actually sent (settings, middleware, web server configuration), every raw-HTML sink in the frontend and server templates and where its data comes from, redirects, and how API errors are shown. Compare the fields each API response carries with the fields the frontend uses. |
| Data and privacy | 8, 9 | Inventory the personal and sensitive data in the models or schemas. For each item, find every way it leaves the database: API responses, exports, reports, emails and notifications, logs, error reports, analytics, admin pages, search, caches, backups, and third parties. Check who can reach each exit. Read the logging and error-reporting configuration and every log call that formats a request, user, or payload. |
| Integrations and back channels | 12, 13 | Find every inbound callback (webhooks, bounce handlers, OAuth callbacks), every outbound call (HTTP clients, SDKs, email, SMS, file storage), every background job, scheduler, and queue consumer, and every management command or operator script. Check signatures, replay, idempotency, SSRF, timeouts, file handling, and the authority each job acts with. |
| Injection and business logic | 6, 14 | Trace untrusted input from each source to each sink in category 6, across files. Then examine the money and state flows: how prices, fees, refunds, and balances are computed, how payment success is confirmed, which state machines exist and whether each transition is guarded, and which operations need transactions, locks, or idempotency keys. |
| Abuse and resilience | 11 | Find every endpoint or job whose cost an outsider controls: authentication and reset, anything that sends email or SMS, search, exports, reports, uploads, imports, and unpaginated lists. Check rate limits, size limits, pagination caps, timeouts, background offloading, and regular expressions applied to input. Check web server and application-server limits in the deployment files. |
| Platform and supply chain | 10, 16, 17 | Read every configuration, settings, deployment, container, web-server, systemd, install-script, and CI workflow file. Review the dependency manifests and lock files, the vendored and generated files, and the binary files the ledger lists (anything that looks like a key, certificate, database, or dump). Search the git history for secrets. Triage the scanner output in `<scratch dir>/scans/` and report only the results you confirm. |

## Reviewer output

```markdown
## Files
- Read in full: <count> files. Not fully read: <path and reason, one per line, or "none">.
  (Cross-cutting and prose reviewers: list each file and mark it `read` or `scanned`.)

## Findings
### <short title>
- Category: <number and name>
- Priority: <P0 | P1 | P2 | P3 | Info>
- Confidence: <Confirmed | Likely | Needs verification>
- Where: <path:line>[, <path:line> ...]
- Issue: <one or two sentences: what is wrong>
- Impact: <who can do what to whom, under what precondition>
- Fix: <the concrete change, naming the function, setting, or library to use>
- Effort: <S | M | L>

## Leads
- <path:line>: <what someone should trace across files, and why>

## Controls verified
- <a control checked and found sound, with its location>
```

Keep each finding to the fields above. Do not paste code longer than three lines. If there
are no findings, write "None" under Findings and still list the controls you verified.
