---
name: bug-report
description: Standards for writing clear, reproducible bug reports for the CalDART web application, with severity, evidence, and environment details. Use when writing, filing, or reviewing a bug report or GitHub issue.
---

# Bug Report Standards

## 1. Core Components

Every bug report MUST include:

- **Clear title** — Describes the symptom and its location (e.g., "Leader status card shows an expired medical as current").
- **Reproduction steps** — Numbered, minimal steps anyone can follow from a fresh demo database.
- **Expected vs. actual behavior** — Side-by-side comparison.
- **Environment** — Commit, where it ran, page, role, browser, and the other fields in the template below.
- **Severity** — Assessed per the scale below.
- **Evidence** — Tracebacks, API responses, log output, or screenshots of incorrect results.

## 2. Severity Scale

| Level | Criteria |
|-------|----------|
| **Critical** | Crash, data corruption, silent wrong results, or security vulnerability. |
| **High** | Major feature broken or blocking for many users. |
| **Medium** | Non-critical feature broken or produces degraded results. |
| **Low** | Minor issue, documentation error, or cosmetic problem. |
| **Trivial** | Very minor issue with negligible user impact. |

## 3. Report Template

```markdown
# Bug Report: [Concise title]

## Description
[1-2 sentences: what is broken and its impact.]

## Environment
- **Commit / branch**: [e.g., 042cee6 on main]
- **Where**: [local dev (`caldart.settings.dev`), production (`caldart.settings.prod`), or the `make e2e` server]
- **URL / page**: [e.g., /portal/profile]
- **Signed-in role(s)**: [e.g., member, dart_leader — or the demo account used]
- **Browser and version** (UI bugs): [e.g., Firefox 142]
- **OS**: [e.g., Ubuntu 24.04, macOS 15, Windows 11]
- **Payment provider** (payment bugs): [mock, Stripe (test/live), or PayPal (sandbox/live)]
- **Python / Node versions** (development-environment bugs): [output of `uv run python --version` and `node --version`]

## Severity
[Level] — [Brief justification]

## Steps to Reproduce
1. `make reset` (fresh demo data), then `make run`.
2. Sign in at http://localhost:8000/portal/ as [demo account from the README's "Demo accounts"].
3. [Action].
4. Observe the error.

## Expected Behavior
[What should happen.]

## Actual Behavior
[What actually happens, including the full traceback.]

## Traceback / Logs / Screenshots / Other Evidence
[Paste the full traceback from the `make run` terminal, browser console errors, the API
request and response body (browser DevTools, Network tab), the email as it appears in
Mailpit (http://localhost:8025/) for email bugs, screenshots, or other relevant evidence
when available]

## Additional Notes
[Workarounds, frequency, related issues.]

## Possible Fix
[Optional: suspected root cause or fix direction.]
```

## 4. Writing Guidelines

1. Be objective and factual — no blame or subjective language.
2. One issue per report.
3. Include the exact commit, version numbers, and full tracebacks.
4. Keep reproduction steps as short as possible while remaining unambiguous.
5. Verify the bug is reproducible before submitting.
6. Redact secrets (API keys, `.env` values, webhook secrets) and real members' personal data from all evidence (see `security`).

## 5. Adaptation

Add bug-specific fields where they help pin the problem down, e.g. the membership plan and status, the DART, or the aircraft N-number involved.
