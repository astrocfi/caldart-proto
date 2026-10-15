---
name: security-audit
description: Full security audit of the current repository (backend, frontend, the interface between them, configuration, deployment, CI, and git history) that reads every file through parallel reviewer subagents and writes a concise report organized by category, with prioritized, actionable findings and a prompt for fixing them. Report only, no code changes. Use when the user asks for a security audit, a security review of the whole codebase, a vulnerability assessment, or a threat review. For only the pending changes on a branch, use a diff-scoped security review instead.
---

# Security Audit

Audit the whole repository for security weaknesses and write a **report only**: do not
change code, configuration, or tests. The skill is stack-agnostic; it adapts to whatever the
inventory finds.

The audit covers every category in [checklist.md](checklist.md): authentication, MFA,
sessions, authorization, CSRF and cross-origin controls, injection, XSS and client-side
security, data protection and privacy, logging and error handling, secrets and
cryptography, denial of service, back channels and integrations, file handling, business
logic and race conditions, the API between frontend and backend, configuration and
deployment, supply chain and CI, and security testing.

## Ground rules

- **Read-only.** Never edit, commit, or push repository files. Never probe a deployed
  system. Run the application locally for dynamic checks only when the user asks.
- **No code goes unread.** Every file in the ledger is assigned to a reviewer, and the
  report states exactly which files were read in full, which were scanned, and which were
  not read and why.
- **Findings are verified.** A scanner hit or a pattern match is a lead. Every reported
  finding cites `path:line`, names the attacker and precondition, and was confirmed by
  reading the code; anything less carries a lower confidence label.
- **Secrets are redacted.** Never repeat a credential in the report, an issue, or chat:
  give its location, kind, and at most its first four characters.
- **The report is sensitive.** It describes unfixed vulnerabilities. Check the
  repository's visibility (`gh repo view --json visibility`, or the remote host); for a
  public repository, warn the user that committing the report or filing public issues
  discloses the findings.
- **Scanners are ad hoc.** Run them through `uvx`, `npx -y`, or an installed binary; never
  add them as dependencies; never let one upload code or results.

## Project standards

Before reviewing, collect the repository's own standards and treat them as authoritative:
agent instruction files (`CLAUDE.md`, `AGENTS.md`, `.claude/rules/*.md`, `.cursor/rules`),
`SECURITY.md`, `CONTRIBUTING`, and documentation pages that describe permissions, roles,
data handling, configuration, or deployment. A documented permission matrix is the
specification the access-control reviewer compares the code against. Cite a standard by
file name when a finding violates it, and report a standard that is itself insecure. When
the repository doesn't have a security standard, use the OWASP ASVS (level 2), the OWASP Top 10,
and the OWASP API Security Top 10 as the baseline.

## Workflow

Keep working files in the session scratchpad (or a temporary directory outside the
repository): `<scratch>/brief.md`, `<scratch>/ledger.json`, `<scratch>/scans/`,
`<scratch>/findings/`. Write each reviewer's answer to `<scratch>/findings/<id>.md` as it
arrives, so the audit survives a context compaction.

### 1. Scope

Default to the whole repository at `HEAD`, tracked files only. Note uncommitted changes and
untracked files in the report; include them (`--include-untracked`) only if the user asks.
If the user names a path or asks for a quick audit, see **Quick and narrowed audits**.

### 2. Threat-model brief

Read the README, the standards above, the dependency manifests, the entry points (URL
configuration, routers, `main` modules, frontend bootstrap), settings, and deployment
files. Write `<scratch>/brief.md`, at most about 60 lines:

- Stack and components (backend framework, frontend framework, database, queues, web
  server, hosting) and the stacks to use from [patterns.md](patterns.md).
- Actors and roles, from anonymous visitor to administrator, and what each may do.
- Assets: the personal and sensitive data held, money flows, credentials, and
  administrative powers.
- Entry points and trust boundaries: public pages, the API, admin and CMS, webhooks,
  scheduled jobs, management commands, and outbound integrations.
- Authentication mechanisms (sessions, tokens, SSO, MFA) and where they are configured.
- Where the documented permission matrix and data rules live, if anywhere.

### 3. Inventory and slicing

```bash
python3 <skill dir>/scripts/inventory.py --out <scratch>/ledger.json
```

The script lists every file, classifies it (`code`, `test`, `prose`, `lock`, `vendored`,
`binary`), counts lines, and packs `code`, `test`, and `prose` files into slices one
reviewer can read in full (`--budget`, default 5,000 lines of code per slice; test and
prose slices are larger). Check the classification: move a misfiled file to the right class
in the ledger, and make sure no application code sits under `vendored`. Tell the user in
one line how many files, lines, and slices there are, then continue.

### 4. Scanners

Start the scanners from [patterns.md](patterns.md) that fit the stack, in the background,
writing to `<scratch>/scans/`. They run while the reviewers work; the platform reviewer
triages their output.

### 5. Reviewers

Launch the reviewers with the prompts in [prompts.md](prompts.md):

- one **slice reviewer** per slice in the ledger;
- the eight **cross-cutting reviewers** (identity, access control, interface and browser,
  data and privacy, integrations and back channels, injection and business logic, abuse
  and resilience, platform and supply chain).

Run them in waves of at most eight concurrent subagents, cross-cutting reviewers in the
first wave, and start the next reviewer as each one finishes. Reviewers write their own
answers to `<scratch>/findings/` and return a short summary. Scanners that finish after the
platform reviewer starts get a separate scanner-triage reviewer. Give later reviewers the
list of issues already reported, so they confirm or extend rather than repeat.

### 6. Coverage check

Compare the reviewers' file lists with the ledger. Every `code` and `test` file must be
read in full by some reviewer, every `prose` file read or scanned, and every `lock`,
`vendored`, and `binary` file covered by the platform reviewer. Send any gap to a new slice
reviewer. A count that differs from the slice size, or a file no reviewer names, is a gap
too: send those files to a gap reviewer. A file that still could not be read goes into the
report's Coverage section with the reason.

### 7. Consolidate and verify

- With more than a dozen reviewer files, delegate the merge to a consolidator subagent
  that writes `<scratch>/merged.md` (deduplicated findings with every location and source,
  disagreements resolved, chains, leads, controls, coverage notes), then work from that.
- Merge duplicates: one root cause is one finding listing every location.
- Verify every P0 and P1 yourself by reading the cited code (for many, delegate to
  verifier subagents with the finding and the instruction to refute it). Drop what does not
  hold; lower the confidence of what cannot be settled from the code.
- Follow the reviewers' leads that no other reviewer settled.
- Look for chains: two modest findings that together give an attacker more (an open
  redirect plus a token in the URL, a stored XSS plus a cookie without `HttpOnly`) become one
  finding at the combined priority.
- Assign final priorities with the rubric below, then number the findings `SEC-001`,
  `SEC-002`, ... by priority, then category.

### 8. Write the report

Use the template below. Write it to `<dir>/YYYY-MM-DD-security-audit.md` when the
repository has a directory for review reports (such as `critiques/`, `reviews/`, `audits/`,
or `reports/`); otherwise to the scratchpad. Do not commit it. In chat, give the path, the
count per priority, and the "Fix first" list, nothing more.

### 9. Offer follow-up

Offer, never do without a yes:

- **Issues** for the P0 and P1 findings (and P2 if the user wants), one per finding,
  following the repository's bug-report and label conventions. For a public repository,
  recommend GitHub private security advisories
  (`gh api -X POST repos/<owner>/<repo>/security-advisories`) instead of public issues.
- **Fixes**, using the prompt at the end of the report, on a branch, one finding or one
  category per pull request.

## Priority rubric

Rate likelihood (who can reach it, with what precondition) against impact (what they gain).

| Priority | Meaning | Examples | Act |
| --- | --- | --- | --- |
| **P0** Critical | Exploitable now by an anonymous or low-privilege attacker, with severe impact | authentication bypass, SQL or command injection, IDOR on personal or financial data, secret in a public repository, payment amount from the client | Fix before anything else; consider taking the feature offline |
| **P1** High | Exploitable with a realistic precondition, or a missing control that is a standard expectation | no MFA for administrators, no login throttling, stored XSS by a signed-in user, CSRF on a state change, reset token reuse | Fix in the current cycle |
| **P2** Medium | Defense-in-depth gap, limited exposure, or hard to exploit | missing CSP, verbose errors, over-broad serializer to a trusted role, missing rate limit on an expensive report | Schedule |
| **P3** Low | Hardening and best practice | header polish, missing negative test, weak but unexploitable configuration | When convenient |
| **Info** | Observation or accepted risk | a deliberate trade-off worth recording | None |

Each finding also carries a **confidence** (Confirmed, Likely, Needs verification) and an
**effort** (S under an hour, M under a day, L more).

## Report template

Keep it concise: one short block per finding, no code longer than three lines, no scanner
dumps. Omit a category's findings block when it doesn't have any, but keep its heading with one line
saying what was checked.

```markdown
# Security audit: <repository> @ <short sha>

**Date:** YYYY-MM-DD. **Scope:** <whole repository | paths>. **Coverage:** <n> of <n> files
(<lines> lines) read in full or scanned; see Coverage.

> Contains unfixed vulnerabilities. Do not publish this report or file its findings as
> public issues on a public repository.

## Summary

<3 to 5 sentences: overall posture, the most serious risks, the strongest controls.>

| P0 | P1 | P2 | P3 | Info |
| --- | --- | --- | --- | --- |
| n | n | n | n | n |

## Fix first

1. **SEC-001** (P0, effort S): <one line>.
2. ...

## Findings by category

### 1. Authentication

#### SEC-003: <title>
**P1** · Confirmed · Effort S
- **Where:** `path/to/file.py:42`, `path/to/other.ts:17`
- **Issue:** <what is wrong>
- **Impact:** <attacker, precondition, outcome>
- **Fix:** <the concrete change>
- **Standard:** <rule file or ASVS/OWASP reference, when one applies>

### 2. Multi-factor authentication

No findings. Checked: <the controls checked, in one line>.

<... categories 3 to 18, in checklist order ...>

## Controls verified

- <control>: <where>. <one line each; the strongest controls first>

## Coverage and method

| Class | Files | Lines | Read in full | Scanned | Not read |
| --- | --- | --- | --- | --- | --- |

- Not read: <path: reason>, or "none".
- Reviewers: <n> slice reviewers, <n> cross-cutting reviewers (<any skipped, and why>).
- Scanners: <tool and version: ran | failed (why) | not applicable>.
- Outside the audit: <production configuration and infrastructure not in the repository,
  dynamic testing, third-party services, anything the user excluded>.

## Prompt for an AI agent to fix the findings

<A self-contained prompt that: names the repository and commit; lists the findings to fix
with their IDs, locations, and fixes; tells the agent to read the project's standards first,
work on a branch, fix one finding or category per pull request, add a test that fails
before each fix and passes after, run the project's checks, and not weaken any test; and
says which findings need a decision from the owner before fixing.>
```

## Quick and narrowed audits

- **Quick:** when the user asks for a quick or high-level audit, skip the slice reviewers
  and run the brief, the scanners, and the eight cross-cutting reviewers. Mark the report's
  Coverage as partial and list what was not read.
- **Narrowed:** for a path or component, inventory only that path, but keep the
  cross-cutting reviewers' view of the interfaces it touches (the routes that reach it, the
  data it exposes).

## Reference

[reference.md](reference.md) has example findings at each priority and the false positives
reviewers most often report.
