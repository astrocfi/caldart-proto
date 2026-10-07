/**
 * The msw handlers the three System pages read as they mount, for the page tests.
 *
 * The email log, its purposes, the report columns, and the registry's state are
 * answered by the shared defaults in `src/test/handlers.ts`; these add the health
 * check, the mail delivery check, the backup list, and the reminder log, which only
 * these pages read.
 */
import { HttpResponse, http } from 'msw';
import type { HttpHandler } from 'msw';

import { API } from '@test/handlers';

/** The health payload the pages' tests answer with: every check well. */
export const HEALTHY = {
  db: 'ok',
  pending_migrations: 0,
  disk_free_mb: 40_960,
  last_backup: '2026-06-15T12:00:00Z',
  version: '0.1.0',
  debug: false,
};

/** The mail delivery payload the pages' tests answer with: one line, good. */
export const MAIL_DELIVERY = {
  domain: 'example.org',
  checked_at: '2026-06-15T12:00:00Z',
  findings: [
    { name: 'Approved senders (SPF)', status: 'pass', detail: 'It is in place.', fix: '' },
  ],
};

/** Handlers for every request a System page makes on mount, with nothing to list. */
export function systemPageHandlers(): HttpHandler[] {
  return [
    http.get(`${API}/system/health`, () => HttpResponse.json(HEALTHY)),
    http.get(`${API}/mail/delivery-check`, () => HttpResponse.json(MAIL_DELIVERY)),
    http.get(`${API}/system/backups`, () => HttpResponse.json([])),
    http.get(`${API}/admin/reminders/log`, () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
  ];
}
