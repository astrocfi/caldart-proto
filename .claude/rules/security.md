---
description: Security best practices for the CalDART web application — secrets, dependencies, input validation, and defensive coding.
---

# Security Best Practices

## 1. Secrets Management

- NEVER commit secrets, API keys, tokens, passwords, or private keys to the repository.
- Store secrets in environment variables (read by django-environ; `.env` locally, the server's environment in production) or GitHub Secrets for CI.
- Use `.env` files for local development ONLY. `.env` is listed in `.gitignore`; `.env.example` documents each variable with a placeholder, never a real value.
- If a secret is accidentally committed, rotate it immediately — deleting the commit is NOT sufficient.

## 2. Dependency Security

- Specify minimum compatible versions for direct dependencies (e.g., `wagtail>=6.3`) in `pyproject.toml`; exact versions are locked in `uv.lock` and `frontend/package-lock.json`.
- Add dependencies only from reputable sources with no known CVEs.
- `make audit` (`uv audit` and `npm audit`) checks every locked package for known
  vulnerabilities, and CI runs it on every push and pull request. Fix a finding by upgrading
  the affected package, not by ignoring it.
- Review changelogs and diffs before merging dependency updates.

## 3. Input Validation

- NEVER trust external input (request bodies, query strings, headers, cookies, uploaded files, webhook payloads, environment variables, data from remote APIs).
- Validate input at the boundary — DRF serializers for the API, Django/Wagtail forms for the CMS — and answer invalid input with a 400 and a clear message before it reaches models or services.
- Compute security-relevant values (prices, amounts, roles, ownership) on the server; never accept them from the client.
- For file paths, resolve to absolute paths and verify they remain within the expected directory (prevent path traversal).

## 4. Safe Defaults

- NEVER implement custom cryptography. Use standard algorithms via trusted libraries (`cryptography`, `hashlib`) and Django's own password, signing, and token utilities.
- When the application downloads or receives external data (including payment webhooks), verify integrity (signatures, checksums, expected schemas) where feasible.
- Do NOT embed credentials, default passwords, or example secrets in source code, tests, or documentation. The only exceptions are clearly fake, local-only values: the demo password in `apps/accounts/seed.py` (documented in the README) and the throwaway `SECRET_KEY`s used by `make e2e` and CI. Never reuse them anywhere real.

## 5. Logging

- NEVER log secrets, tokens, passwords, or full stack traces containing sensitive data.
- Sanitize PII (personally identifiable information) before logging.

## 6. Code Review Security Checklist

When reviewing PRs, verify:

- [ ] No secrets or credentials in code, config, or comments.
- [ ] Request inputs are validated at the serializer/form boundary with clear error messages.
- [ ] Every new endpoint enforces the permission matrix in `docs/developer/api-reference.rst`.
- [ ] New dependencies are from reputable sources and have no known CVEs.
- [ ] File operations guard against path traversal.
- [ ] Error messages do not leak internal file paths or sensitive data.
