# Purpose

<!-- Why is this change needed? What problem does it solve? -->

Closes #<!-- issue number -->

## Changes/Implementation Details

<!-- What changed and how? Note any non-obvious design decisions. Bullet list is fine. -->

-

## Type of Change

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change (fix or feature that alters existing behavior or the API contract)
- [ ] Refactor (no functional or API changes)
- [ ] Documentation
- [ ] Tests only (no production code change)
- [ ] CI / Build / Dependencies

## Testing

- [ ] Backend tests pass (`make test-backend`)
- [ ] Frontend tests pass (`make test-frontend`)
- [ ] End-to-end tests pass (`make e2e`, if the change touches the end-to-end flows)
- [ ] New or updated tests for changed code
- [ ] Tested manually (describe below if applicable)

<!-- Manual verification steps, if any: the demo account used, the pages visited, what you saw. -->

## Potential Impacts

<!-- Effects on the API contract (PLAN.rst §6) and the frontend that consumes it, database
     migrations, new or changed settings and environment variables (.env.example), role
     permissions (PLAN.rst §5), payment providers, performance, or deployment (deploy/).
     Write "None" if straightforward. -->

## Checklist

- [ ] `make lint test check docs audit` all pass
- [ ] Type annotations on new and modified code (Python and TypeScript)
- [ ] No secrets or credentials committed
- [ ] No warnings or errors introduced (CI, linters, type checking, builds) or justified in Notes
- [ ] Docstrings, docs pages (`docs/`), and the README updated (if applicable)
- [ ] `PLAN.rst` updated in this PR if the change departs from it
- [ ] No temporary or debug code left in
- [ ] Performance impact assessed (see Potential Impacts above)
- [ ] Breaking changes flagged in Type of Change above

## Notes

<!-- Anything reviewers should know: tricky areas, unresolved questions, follow-up
     work. Say "None" if nothing relevant. -->
