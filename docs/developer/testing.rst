=======
Testing
=======

How the suites are organised and run: pytest-django against Postgres with
per-branch databases, the model factories and shared fixtures, mocking the
Stripe and PayPal HTTP calls, frozen clocks for the reminder scanner, vitest
plus Testing Library and msw on the frontend, the Playwright end-to-end specs
for the five headline flows, and what CI runs on every pull request.  This
page is owned by ``feat/integration-qa`` in Phase 3, per PLAN §15.
