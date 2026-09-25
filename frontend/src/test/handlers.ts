import { HttpResponse, http } from 'msw';
import type { HttpHandler } from 'msw';

import type {
  MembershipStatus,
  Payment,
  PaymentPeriodSummary,
  Plan,
  ReportColumn,
  RoleSlug,
  User,
} from '../portal/api/types';

export const API = '/api/v1';

/** The value the default `GET /auth/csrf` handler hands out. */
export const TEST_CSRF_TOKEN = 'test-csrf-token';

export const NO_MEMBERSHIP: MembershipStatus = {
  status: 'none',
  expires_on: null,
  plan: null,
  is_lifetime: false,
};

export const CURRENT_MEMBERSHIP: MembershipStatus = {
  status: 'current',
  expires_on: '2027-06-30',
  plan: 'Annual',
  is_lifetime: false,
};

/** A membership that never runs out, for the screens a life member reads. */
export const LIFETIME_MEMBERSHIP: MembershipStatus = {
  status: 'current',
  expires_on: null,
  plan: 'Life',
  is_lifetime: true,
};

/** Build a `user` payload without repeating every field in each test. */
export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: 1,
    email: 'member@example.org',
    first_name: 'Marta',
    last_name: 'Reyes',
    roles: ['member'] as RoleSlug[],
    is_active: true,
    membership: CURRENT_MEMBERSHIP,
    profile_complete: true,
    ...overrides,
  };
}

/** Default handlers: CSRF works, nobody is signed in, renewal is off. */
export const handlers = [
  http.get(
    `${API}/auth/csrf`,
    () =>
      new HttpResponse(null, {
        status: 204,
        headers: { 'Set-Cookie': `csrftoken=${TEST_CSRF_TOKEN}; path=/` },
      }),
  ),
  http.get(`${API}/auth/me`, () =>
    HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 }),
  ),
  // Every screen that carries the renewal state reads this, so the default keeps
  // a suite that is not about renewal from having to declare one.
  http.get(`${API}/me/renewal`, () => HttpResponse.json({ mandate: null })),
  // Every report screen reads its column registry as it mounts.  An empty
  // registry leaves the exports on the server's own default columns, so a suite
  // that is not about columns does not have to declare one.
  http.get(`${API}/admin/members/columns`, () => HttpResponse.json([])),
  http.get(`${API}/admin/aircraft/columns`, () => HttpResponse.json([])),
  // The reports the caller may read and each report's column registry, empty
  // for the same reason: a suite that is not about reports need not declare one.
  http.get(`${API}/reports`, () => HttpResponse.json([])),
  http.get(`${API}/reports/:slug/columns`, () => HttpResponse.json([])),
  // The aircraft record reads its history as it mounts.  An empty history keeps
  // a suite that is not about the history from having to declare one.
  http.get(`${API}/aircraft/:id/changes`, () => HttpResponse.json([])),
  // The email log panel reads this as `/portal/system` mounts, so a suite that
  // is not about the log does not have to declare one.
  http.get(`${API}/system/emails`, () =>
    HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
  ),
];

/** Convenience: make `/auth/me` answer with `user`. */
export function signedInAs(user: User): HttpHandler {
  return http.get(`${API}/auth/me`, () => HttpResponse.json(user));
}

/**
 * The finance endpoints the `/admin/payments` screens read, answering with
 * whatever the caller passes.
 *
 * Every request URL is pushed onto `urls`, so a test can assert that a filter,
 * a column choice or an ordering really reached the server rather than only
 * changing the screen.
 */
export interface FinanceStub {
  payments?: Payment[];
  summary?: PaymentPeriodSummary[];
  columns?: ReportColumn[];
  plans?: Plan[];
  urls?: string[];
}

/** Handlers for the finance list, summary, columns and plan catalog. */
export function financeHandlers({
  payments = [],
  summary = [],
  columns = [],
  plans = [],
  urls = [],
}: FinanceStub = {}): HttpHandler[] {
  const record = (request: Request) => urls.push(request.url);
  return [
    http.get(`${API}/admin/payments/summary`, ({ request }) => {
      record(request);
      return HttpResponse.json(summary);
    }),
    http.get(`${API}/admin/payments/columns`, ({ request }) => {
      record(request);
      return HttpResponse.json(columns);
    }),
    http.get(`${API}/admin/payments`, ({ request }) => {
      record(request);
      return HttpResponse.json({
        count: payments.length,
        next: null,
        previous: null,
        results: payments,
      });
    }),
    http.get(`${API}/plans`, () => HttpResponse.json(plans)),
  ];
}
