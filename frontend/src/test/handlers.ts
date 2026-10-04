import { HttpResponse, http } from 'msw';
import type { HttpHandler } from 'msw';

import type {
  AdminUser,
  DonorRow,
  MembershipStatus,
  NotificationEvent,
  NotificationSubscription,
  NotificationSubscriptionCreate,
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
import type {
  InsuranceVerificationPayload,
  MemberVerificationPayload,
  ProfileVerification,
  Verification,
  AircraftDetail,
  AircraftSummary,
  BulkEmailSender,
  LeaderStatus,
  Profile,
  SendableEmailType,
  VerifierGrantPayload,
} from '@/portal/api/types';
import type { ReportSlug } from '../portal/reports/types';
import { TEST_AIRCRAFT_TYPES, makeAircraftType, makeProfile } from './fixtures/profile';
import { makeRegistryStatus } from './fixtures/registry';
import { makeReminderSchedule } from './fixtures/reminders';

/**
 * The API base the handlers answer under, whatever URL prefix is in front of it: a
 * test that serves the page under a prefix is answered by the same handlers.
 */
export const API = '*/api/v1';

/** The value the default `GET /auth/csrf` handler hands out. */
export const TEST_CSRF_TOKEN = 'test-csrf-token';

/** What an account holding no paid membership reads as, whichever kind it chose: a friend. */
export const NO_MEMBERSHIP: MembershipStatus = {
  status: 'friend',
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
    kind: 'member',
    friend_on: null,
    ...overrides,
  };
}

/**
 * Build an `/admin/users/{id}` payload: `makeUser`, plus when the address was
 * verified, keeping `email_verified` in step with `email_verified_at` the way
 * the server does, and no bounce unless `email_bounced_at` names one.
 */
export function makeAdminUser(overrides: Partial<AdminUser> = {}): AdminUser {
  const {
    email_verified_at = '2024-07-01T12:05:00Z',
    email_bounced_at = null,
    email_bounce_detail = '',
    ...userOverrides
  } = overrides;
  return {
    ...makeUser(userOverrides),
    email_verified: email_verified_at !== null,
    email_verified_at,
    email_bounced_at,
    email_bounce_detail,
    reactivation_blocked: false,
  };
}

/** Build a `GET /admin/payments/donors` row without repeating every field in each test. */
export function makeDonorRow(overrides: Partial<DonorRow> = {}): DonorRow {
  return {
    user_id: 1,
    name: 'Dana Doe',
    email: 'dana@example.org',
    phone: '415-555-0100',
    city: 'Concord',
    state: 'CA',
    county: 'Contra Costa',
    dart: '',
    first_gift: '2026-01-10',
    last_gift: '2026-01-10',
    gifts: 1,
    given_cents: 5000,
    refunded_cents: 0,
    net_cents: 5000,
    active: true,
    is_tombstone: false,
    ...overrides,
  };
}

/** Default handlers: CSRF works, nobody is signed in, renewal and donation are off. */
/** The email types the default handler says the signed-in sender may send. */
export const SENDABLE_TYPES: SendableEmailType[] = [
  {
    id: 1,
    name: 'Operational',
    description: 'News about how CalDART runs.',
    allow_opt_out: true,
  },
  {
    id: 3,
    name: 'Mission',
    description: 'Requests for pilots and aircraft.',
    allow_opt_out: true,
  },
];

/** Who the default handler says the signed-in sender may send to: CalDART management. */
export const MANAGEMENT_SENDER: BulkEmailSender = {
  is_management: true,
  can_send: true,
  reason: '',
  dart: null,
  dart_name: '',
  default_reply_to: 'office@caldart.org',
};

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
  // The same for the recurring donation, which the Payments screen, the checkout
  // and a life member's dashboard read.
  http.get(`${API}/me/donation`, () => HttpResponse.json({ mandate: null })),
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
  // The aircraft type picker searches this; the default answers the fixture
  // types whose make and model contain what was typed.
  http.get(`${API}/aircraft/types`, ({ request }) => {
    const typed = (new URL(request.url).searchParams.get('q') ?? '').trim().toLowerCase();
    const found = TEST_AIRCRAFT_TYPES.filter(
      (type) => typed !== '' && `${type.make} ${type.model}`.toLowerCase().includes(typed),
    );
    return HttpResponse.json(found);
  }),
  // The register's header and the Health & Database page read the registry's state as
  // they mount: by default, one successful import and none running.
  http.get(`${API}/aircraft/registry`, () => HttpResponse.json(makeRegistryStatus())),
  // Both reminder screens read the reminder schedule; by default nobody has changed it.
  http.get(`${API}/admin/reminders/schedule`, () => HttpResponse.json(makeReminderSchedule())),
  // My aircraft and the register read the coverage policy; by default it excludes nothing.
  http.get(`${API}/aircraft/coverage-policy`, () =>
    HttpResponse.json({ excluded_categories: [], excluded_airworthiness: [], note: '' }),
  ),
  // The N-number typeahead on the aircraft form asks this as the box is typed into;
  // by default no registration starts with what was typed, so no list opens.
  http.get(`${API}/aircraft/registrations`, () => HttpResponse.json([])),
  // One registration by its N-number; by default the registry has no such registration.
  http.get(`${API}/aircraft/registry/:nNumber`, ({ params }) =>
    HttpResponse.json(
      { detail: `No registration for ${String(params.nNumber)} in the registry.` },
      { status: 404 },
    ),
  ),
  // The Sent Emails page reads this as it mounts, so a suite that
  // is not about the log does not have to declare one.
  http.get(`${API}/system/emails`, () =>
    HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
  ),
  // The profile form's Address box asks for suggestions as it is typed into.  No
  // suggestions is also what the server answers while the feature is off.
  http.get(`${API}/addresses/suggest`, () => HttpResponse.json([])),
  // The purposes its filter offers, read as it mounts too.
  http.get(`${API}/system/emails/purposes`, () =>
    HttpResponse.json([
      { value: 'receipt', label: 'Receipt' },
      { value: 'password_reset', label: 'Password reset' },
    ]),
  ),
  // The compose screen's type choice reads the types the sender may send.
  http.get(`${API}/email-types/sendable`, () => HttpResponse.json(SENDABLE_TYPES)),
  // The bulk email screens read who the sender may send to.
  http.get(`${API}/bulk-email/sender`, () => HttpResponse.json(MANAGEMENT_SENDER)),
  // The member record's Email preferences card reads these as the record opens.
  http.get(`${API}/admin/members/:id/email-preferences`, () => HttpResponse.json([])),
];

/** What `POST /auth/login` answers for a deactivated account whose password matched. */
export const DEACTIVATED_LOGIN = {
  detail: 'This account is deactivated. You can reactivate it.',
  code: 'deactivated',
} as const;

/** Make `POST /auth/login` refuse as it does a deactivated account with the right password. */
export function signInDeactivated(): HttpHandler {
  return http.post(`${API}/auth/login`, () =>
    HttpResponse.json(DEACTIVATED_LOGIN, { status: 403 }),
  );
}

/** What the kind handlers saw: each `POST /me/kind/friend` body, and each undo. */
export interface KindSwitchCalls {
  bodies: unknown[];
  undos: number;
}

/**
 * `POST` and `DELETE /me/kind/friend`, answering with `become` and `undo` (the user
 * payloads the server returns) and recording each call in `calls`.
 */
export function kindSwitchHandlers({
  become,
  undo,
  calls,
}: {
  become: User;
  undo: User;
  calls: KindSwitchCalls;
}): HttpHandler[] {
  return [
    http.post(`${API}/me/kind/friend`, async ({ request }) => {
      calls.bodies.push(await request.json());
      return HttpResponse.json(become);
    }),
    http.delete(`${API}/me/kind/friend`, () => {
      calls.undos += 1;
      return HttpResponse.json(undo);
    }),
  ];
}

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

/**
 * Handlers for the reports screen's reads, answering with whatever the caller
 * passes.  A `PATCH` of a listed subscription merges its body into that one and
 * answers with it, so the list read after an edit shows the change.
 */
export function subscriptionHandlers({
  reports = [],
  subscriptions = [],
  rosters = [],
}: ReportsStub = {}): HttpHandler[] {
  let store = [...subscriptions];
  return [
    http.get(`${API}/reports`, () => HttpResponse.json(reports)),
    http.get(`${API}/reports/subscriptions`, () => HttpResponse.json(store)),
    http.patch(`${API}/reports/subscriptions/:id`, async ({ params, request }) => {
      const id = Number(params.id);
      const current = store.find((subscription) => subscription.id === id);
      if (current === undefined) return new HttpResponse(null, { status: 404 });
      const patch = (await request.json()) as Partial<ReportSubscription>;
      const changed = { ...current, ...patch };
      store = store.map((subscription) => (subscription.id === id ? changed : subscription));
      return HttpResponse.json(changed);
    }),
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

/** Who may receive each category's events, as the server's catalog names them. */
const MEMBERSHIP_ROLES: NotificationEvent['roles'] = ['account_admin', 'user_admin'];
const MONEY_ROLES: NotificationEvent['roles'] = ['treasurer', 'account_admin'];
const ACCOUNT_ROLES: NotificationEvent['roles'] = ['user_admin', 'account_admin'];

/** One catalog entry, in the order its fields are listed. */
function notificationEvent(
  slug: string,
  label: string,
  category: NotificationEvent['category'],
  description: string,
  roles: NotificationEvent['roles'],
): NotificationEvent {
  return { slug, label, category, description, roles };
}

/** The server's catalog of notification events, in its order, as `GET /notifications/events` lists it. */
export const NOTIFICATION_EVENTS: NotificationEvent[] = [
  notificationEvent(
    'signed_up',
    'Sign-up',
    'Membership',
    'Somebody registered on the site.',
    MEMBERSHIP_ROLES,
  ),
  notificationEvent(
    'member_added',
    'Member added by an administrator',
    'Membership',
    'An administrator created a member or friend by hand.',
    MEMBERSHIP_ROLES,
  ),
  notificationEvent(
    'became_friend',
    'Member became a friend',
    'Membership',
    'A member became a friend.',
    MEMBERSHIP_ROLES,
  ),
  notificationEvent(
    'became_member',
    'Friend became a member',
    'Membership',
    'A friend became a member.',
    MEMBERSHIP_ROLES,
  ),
  notificationEvent(
    'membership_paid',
    'Membership paid',
    'Membership',
    'A payment started a term.',
    MEMBERSHIP_ROLES,
  ),
  notificationEvent(
    'membership_granted',
    'Membership granted by an administrator',
    'Membership',
    'An administrator granted a membership.',
    MEMBERSHIP_ROLES,
  ),
  notificationEvent(
    'membership_expired',
    'Membership expired',
    'Membership',
    'A membership ran out.',
    MEMBERSHIP_ROLES,
  ),
  notificationEvent(
    'auto_renewal_on',
    'Automatic payment turned on',
    'Money',
    'Somebody set up an automatic payment.',
    MONEY_ROLES,
  ),
  notificationEvent(
    'auto_renewal_off',
    'Automatic payment turned off',
    'Money',
    'An automatic payment was turned off.',
    MONEY_ROLES,
  ),
  notificationEvent(
    'auto_renewal_declined',
    'Automatic payment declined',
    'Money',
    'An automatic charge was declined.',
    MONEY_ROLES,
  ),
  notificationEvent(
    'donation_received',
    'Donation received',
    'Money',
    'A gift arrived.',
    MONEY_ROLES,
  ),
  notificationEvent(
    'payment_recorded',
    'Payment recorded by hand',
    'Money',
    'The treasurer recorded a payment.',
    MONEY_ROLES,
  ),
  notificationEvent(
    'payment_refunded',
    'Payment refunded',
    'Money',
    'A payment was refunded.',
    MONEY_ROLES,
  ),
  notificationEvent(
    'account_deactivated',
    'Account deactivated',
    'Accounts',
    'An account was deactivated.',
    ACCOUNT_ROLES,
  ),
  notificationEvent(
    'account_reactivated',
    'Account reactivated',
    'Accounts',
    'A deactivated account was brought back.',
    ACCOUNT_ROLES,
  ),
  notificationEvent(
    'roles_changed',
    'Roles changed',
    'Accounts',
    'A role was granted or taken away.',
    ACCOUNT_ROLES,
  ),
  notificationEvent(
    'email_changed',
    'Email address changed',
    'Accounts',
    'Somebody changed their address.',
    ACCOUNT_ROLES,
  ),
  notificationEvent(
    'profile_changed',
    'Profile changed',
    'Accounts',
    'A profile was edited.',
    ACCOUNT_ROLES,
  ),
  notificationEvent('aircraft_added', 'Aircraft added', 'Aircraft', 'An aircraft was added.', [
    'account_admin',
  ]),
  notificationEvent(
    'aircraft_changed',
    'Aircraft changed',
    'Aircraft',
    "An aircraft's details changed.",
    ['account_admin'],
  ),
  notificationEvent(
    'aircraft_removed',
    'Aircraft removed',
    'Aircraft',
    'An aircraft was taken off a list.',
    ['account_admin'],
  ),
];

/** What the `/admin/notifications` screen reads as it mounts. */
export interface NotificationsStub {
  events?: NotificationEvent[];
  subscriptions?: NotificationSubscription[];
}

/**
 * Handlers for the notifications screen, answering with whatever the caller
 * passes.  They keep the subscriptions in a store: a `POST` adds one bound to
 * no account, a `PATCH` merges its body into the one it names, and a `DELETE`
 * drops it, so the list read after each shows the change.
 */
export function notificationHandlers({
  events = NOTIFICATION_EVENTS,
  subscriptions = [],
}: NotificationsStub = {}): HttpHandler[] {
  let store = [...subscriptions];
  const url = `${API}/notifications/subscriptions`;
  return [
    http.get(`${API}/notifications/events`, () => HttpResponse.json(events)),
    http.get(url, () => HttpResponse.json(store)),
    http.post(url, async ({ request }) => {
      const body = (await request.json()) as NotificationSubscriptionCreate;
      const created = makeNotificationSubscription({
        id: Math.max(0, ...store.map((subscription) => subscription.id)) + 1,
        recipient_user: null,
        recipient_name: '',
        recipient_email: body.recipient_email,
        events: body.events,
      });
      store = [...store, created];
      return HttpResponse.json(created, { status: 201 });
    }),
    http.patch(`${url}/:id`, async ({ params, request }) => {
      const id = Number(params.id);
      const current = store.find((subscription) => subscription.id === id);
      if (current === undefined) return new HttpResponse(null, { status: 404 });
      const patch = (await request.json()) as Partial<NotificationSubscription>;
      const changed = { ...current, ...patch };
      store = store.map((subscription) => (subscription.id === id ? changed : subscription));
      return HttpResponse.json(changed);
    }),
    http.delete(`${url}/:id`, ({ params }) => {
      store = store.filter((subscription) => subscription.id !== Number(params.id));
      return new HttpResponse(null, { status: 204 });
    }),
  ];
}

/** Build a `NotificationSubscription` payload without repeating every field in each test. */
export function makeNotificationSubscription(
  overrides: Partial<NotificationSubscription> = {},
): NotificationSubscription {
  return {
    id: 1,
    recipient_user: 7,
    recipient_name: 'Ada Admin',
    recipient_email: 'ada@example.org',
    events: ['signed_up', 'became_member'],
    is_active: true,
    created_by_name: 'Ada Admin',
    created_at: '2026-09-20T18:00:00Z',
    updated_at: '2026-09-20T18:00:00Z',
    ...overrides,
  };
}

/* ------------------------------------------------------------ verification */

/** An item a verifier checked. */
export const VERIFIED: Verification = {
  verified: true,
  verified_by: 'Dana Leader',
  verified_at: '2026-05-01T16:30:00Z',
};

/** An item nobody has checked, or one a change cleared. */
export const NOT_VERIFIED: Verification = { verified: false, verified_by: null, verified_at: null };

/** All three of a person's items verified. */
export const ALL_VERIFIED: ProfileVerification = {
  certificate: VERIFIED,
  medical: VERIFIED,
  photo_id: VERIFIED,
};

/** None of a person's items verified. */
export const NONE_VERIFIED: ProfileVerification = {
  certificate: NOT_VERIFIED,
  medical: NOT_VERIFIED,
  photo_id: NOT_VERIFIED,
};

/** A `/me/profile` payload with a photo ID and every item verified, `overrides` merged over. */
export function makeVerifiedProfile(overrides: Partial<Profile> = {}): Profile {
  return {
    ...makeProfile(),
    photo_id_type: 'passport',
    verification: ALL_VERIFIED,
    ...overrides,
  };
}

/** An aircraft summary row with current, verified insurance. */
export function makeVerifiedAircraftSummary(
  overrides: Partial<AircraftSummary> = {},
): AircraftSummary {
  return {
    id: 1,
    n_number: 'N172SP',
    make: 'Cessna',
    model: '172S Skyhawk',
    type: makeAircraftType({ id: 1, model: '172S Skyhawk' }),
    category: 'airplane',
    airworthiness: 'standard',
    coverage: { excluded: false, reason: '' },
    insurance_is_current: true,
    insurance_expiration: '2027-03-01',
    insurance_summary: '$1,000,000 / $100,000 · exp 2027-03-01',
    insurance_verified: true,
    ...overrides,
  };
}

/** An aircraft detail payload with current insurance, verified, and one pilot. */
export function makeVerifiedAircraft(overrides: Partial<AircraftDetail> = {}): AircraftDetail {
  const { insurance_verified: _verified, ...summary } = makeVerifiedAircraftSummary();
  return {
    ...summary,
    updated_at: '2026-09-01T12:00:00Z',
    year: 2008,
    owner_type: 'club',
    owner_name: 'Palo Alto Flying Club',
    owner_contact: 'ops@example.org',
    seats: 4,
    insurance_carrier: 'Avemco',
    insurance_policy_number: 'AV-00012345',
    insurance_liability_per_occurrence_cents: 100_000_000,
    insurance_liability_per_person_cents: 10_000_000,
    insurance_hull_cents: 14_500_000,
    notes: '',
    created_by: null,
    is_active: true,
    insurance_verification: VERIFIED,
    pilots: [
      {
        user_id: 7,
        name: 'Marta Reyes',
        email: 'marta@example.org',
        membership_status: 'current',
        medical_is_current: true,
      },
    ],
    ...overrides,
  };
}

/** A member check status card for a current, verified pilot: a GO. */
export function makeLeaderStatus(overrides: Partial<LeaderStatus> = {}): LeaderStatus {
  return {
    name: 'Marta Reyes',
    email: 'marta@example.org',
    phone: '650-555-0100',
    dart: 'Palo Alto',
    membership: { status: 'current', expires_on: '2027-06-30', plan: 'Annual' },
    certificate: {
      type: 'private',
      number: '3181234',
      ratings: ['instrument'],
      verification: VERIFIED,
    },
    medical: { type: 'third', expiration: '2026-12-01', is_current: true, verification: VERIFIED },
    photo_id: { type: 'passport', verification: VERIFIED },
    is_verifier: false,
    aircraft: [makeVerifiedAircraftSummary()],
    go_no_go: { membership: true, medical: true, verified: true },
    ...overrides,
  };
}

/** The requests the verification handlers received, in order. */
export interface VerificationCalls {
  members: { userId: number; body: MemberVerificationPayload }[];
  aircraft: { aircraftId: number; body: InsuranceVerificationPayload }[];
  verifier: { userId: number; body: VerifierGrantPayload }[];
}

/** What the verification handlers answer with. */
export interface VerificationStub {
  /** The status card both member writes answer with. */
  status?: LeaderStatus;
  /** The aircraft the insurance write answers with. */
  aircraft?: AircraftDetail;
}

/**
 * Handlers for the three verification writes, recording each body in `calls` and
 * answering with the stub's status card or aircraft.
 */
export function verificationHandlers(
  calls: VerificationCalls,
  { status = makeLeaderStatus(), aircraft = makeVerifiedAircraft() }: VerificationStub = {},
): HttpHandler[] {
  return [
    http.put(`${API}/leader/members/:id/verification`, async ({ params, request }) => {
      const body = (await request.json()) as MemberVerificationPayload;
      calls.members.push({ userId: Number(params.id), body });
      return HttpResponse.json(status);
    }),
    http.put(`${API}/leader/aircraft/:id/verification`, async ({ params, request }) => {
      const body = (await request.json()) as InsuranceVerificationPayload;
      calls.aircraft.push({ aircraftId: Number(params.id), body });
      return HttpResponse.json(aircraft);
    }),
    http.put(`${API}/leader/members/:id/verifier`, async ({ params, request }) => {
      const body = (await request.json()) as VerifierGrantPayload;
      calls.verifier.push({ userId: Number(params.id), body });
      return HttpResponse.json({ ...status, is_verifier: body.verifier });
    }),
  ];
}

/** An empty record for `verificationHandlers` to fill. */
export function emptyVerificationCalls(): VerificationCalls {
  return { members: [], aircraft: [], verifier: [] };
}
