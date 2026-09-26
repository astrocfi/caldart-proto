import { HttpResponse, http } from 'msw';
import type { HttpHandler } from 'msw';

import type {
  AdminUser,
  MembershipStatus,
  Payment,
  PaymentPeriodSummary,
  Plan,
  ReportColumn,
  ReportSubscription,
  ReportSummary,
  RoleSlug,
  Roster,
  SavedColumnSet,
  SavedColumnSetWrite,
  User,
} from '../portal/api/types';
import type { ReportSlug } from '../portal/reports/types';

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
    email_verified: true,
    ...overrides,
  };
}

/**
 * Build an `/admin/users/{id}` payload: `makeUser`, plus when the address was
 * verified, keeping `email_verified` in step with `email_verified_at` the way
 * the server does.
 */
export function makeAdminUser(overrides: Partial<AdminUser> = {}): AdminUser {
  const { email_verified_at = '2024-07-01T12:05:00Z', ...userOverrides } = overrides;
  return {
    ...makeUser(userOverrides),
    email_verified: email_verified_at !== null,
    email_verified_at,
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
  // The reports the caller may read and each report's column registry, empty
  // for the same reason: a suite that is not about reports need not declare one.
  http.get(`${API}/reports`, () => HttpResponse.json([])),
  http.get(`${API}/reports/:slug/columns`, () => HttpResponse.json([])),
  // The column chooser reads the caller's saved sets when it opens; none by default.
  http.get(`${API}/reports/:slug/column-sets`, () => HttpResponse.json([])),
  // The aircraft record reads its history as it mounts.  An empty history keeps
  // a suite that is not about the history from having to declare one.
  http.get(`${API}/aircraft/:id/changes`, () => HttpResponse.json([])),
  // The email log panel reads this as `/portal/system` mounts, so a suite that
  // is not about the log does not have to declare one.
  http.get(`${API}/system/emails`, () =>
    HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
  ),
  // The purposes its filter offers, read as it mounts too.
  http.get(`${API}/system/emails/purposes`, () =>
    HttpResponse.json([
      { value: 'receipt', label: 'Receipt' },
      { value: 'password_reset', label: 'Password reset' },
    ]),
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
    http.get(`${API}/reports/payments/columns`, ({ request }) => {
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

/** One request the column-set handlers answered, as a test asserts on it. */
export interface ColumnSetRequest {
  method: string;
  url: string;
  body: SavedColumnSetWrite | null;
}

/**
 * A stateful stand-in for one report's saved column sets.
 *
 * `GET` lists the sets by name, `POST` saves one or replaces the columns of the
 * set with that name (answering 201 either way, as the server does), and
 * `DELETE` removes one by id, 404 for an id it does not hold.  `sets` seeds the
 * store, which is copied so a test cannot mutate another's; every request is
 * pushed onto `requests`.
 */
export function columnSetHandlers(
  slug: ReportSlug,
  sets: readonly SavedColumnSet[] = [],
  requests: ColumnSetRequest[] = [],
): HttpHandler[] {
  let store = sets.map((set) => ({ ...set, columns: [...set.columns] }));
  let nextId = Math.max(0, ...store.map((set) => set.id)) + 1;
  const base = `${API}/reports/${slug}/column-sets`;
  const byName = (a: SavedColumnSet, b: SavedColumnSet) => a.name.localeCompare(b.name);
  return [
    http.get(base, ({ request }) => {
      requests.push({ method: 'GET', url: request.url, body: null });
      return HttpResponse.json([...store].sort(byName));
    }),
    http.post(base, async ({ request }) => {
      const body = (await request.json()) as SavedColumnSetWrite;
      requests.push({ method: 'POST', url: request.url, body });
      const existing = store.find((set) => set.name === body.name);
      const saved = { id: existing?.id ?? nextId, name: body.name, columns: body.columns };
      if (existing === undefined) nextId += 1;
      store = [...store.filter((set) => set.id !== saved.id), saved];
      return HttpResponse.json(saved, { status: 201 });
    }),
    http.delete(`${base}/:id`, ({ request, params }) => {
      requests.push({ method: 'DELETE', url: request.url, body: null });
      const id = Number(params.id);
      if (!store.some((set) => set.id === id)) {
        return HttpResponse.json({ detail: 'Not found.' }, { status: 404 });
      }
      store = store.filter((set) => set.id !== id);
      return new HttpResponse(null, { status: 204 });
    }),
  ];
}
/**
 * What the `/admin/reports` screen reads as it mounts: the reports the caller
 * may read, the subscriptions, the DART rosters, and the DART and plan lists
 * the subscription form's filters offer.
 */
export interface ReportsStub {
  reports?: ReportSummary[];
  subscriptions?: ReportSubscription[];
  rosters?: Roster[];
}

/** Handlers for the reports screen's reads, answering with whatever the caller passes. */
export function subscriptionHandlers({
  reports = [],
  subscriptions = [],
  rosters = [],
}: ReportsStub = {}): HttpHandler[] {
  return [
    http.get(`${API}/reports`, () => HttpResponse.json(reports)),
    http.get(`${API}/reports/subscriptions`, () => HttpResponse.json(subscriptions)),
    http.get(`${API}/reports/rosters`, () => HttpResponse.json(rosters)),
    http.get(`${API}/darts`, () => HttpResponse.json([])),
    http.get(`${API}/plans`, () => HttpResponse.json([])),
  ];
}

/** Build a `ReportSubscription` payload without repeating every field in each test. */
export function makeSubscription(overrides: Partial<ReportSubscription> = {}): ReportSubscription {
  return {
    id: 1,
    report: 'members',
    report_title: 'Members',
    recipient_user: 7,
    recipient_name: 'Ada Admin',
    recipient_email: 'ada@example.org',
    filters: {},
    columns: [],
    formats: 'pdf',
    cadence: 'monthly',
    weekday: 0,
    is_active: true,
    created_by_name: 'Ada Admin',
    last_sent_at: null,
    next_due_on: '2026-10-01',
    ...overrides,
  };
}
