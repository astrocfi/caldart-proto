/**
 * TypeScript shapes for every object in the API contract
 * (`docs/developer/api-reference.rst`).
 *
 * Features import from here rather than redeclaring shapes, so keep these in
 * step with the DRF serializers.  Dates are ISO-8601 strings
 * (`YYYY-MM-DD` for dates, full timestamps for datetimes).
 */

export type IsoDate = string;
export type IsoDateTime = string;

export type RoleSlug =
  'member' | 'dart_leader' | 'user_admin' | 'account_admin' | 'website_admin' | 'system_admin';

export interface Role {
  slug: RoleSlug;
  description: string;
}

/* -------------------------------------------------------------- membership */
export type MembershipState = 'current' | 'expired' | 'none';

export interface MembershipStatus {
  status: MembershipState;
  expires_on: IsoDate | null;
  plan: string | null;
  is_lifetime: boolean;
}

export type MembershipTermStatus = 'active' | 'expired' | 'canceled';
export type MembershipSource = 'payment' | 'manual' | 'seed';

export interface MembershipTerm {
  id: number;
  plan: string;
  starts_on: IsoDate;
  ends_on: IsoDate | null;
  status: MembershipTermStatus;
  source: MembershipSource;
}

export interface MembershipDetail extends MembershipStatus {
  history: MembershipTerm[];
}

/* -------------------------------------------------------------------- auth */
export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  roles: RoleSlug[];
  is_active: boolean;
  membership: MembershipStatus;
  profile_complete: boolean;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
}

export interface PasswordChangePayload {
  current_password: string;
  new_password: string;
}

/** `POST /auth/password/reset`. */
export interface PasswordResetRequestPayload {
  email: string;
}

export interface PasswordResetConfirmPayload {
  uid: string;
  token: string;
  new_password: string;
}

/* ------------------------------------------------------ user administration */
/** The writable half of `PATCH /admin/users/{id}`. */
export interface AdminUserPatch {
  first_name?: string;
  last_name?: string;
  email?: string;
  is_active?: boolean;
  roles?: RoleSlug[];
}

/** `POST /admin/users/{id}/send-password-reset`. */
export interface SendPasswordResetResult {
  detail: string;
}

/* ------------------------------------------------------------------ member */
export type PilotCertificateType =
  'none' | 'student' | 'sport' | 'recreational' | 'private' | 'commercial' | 'atp';

export type IfrRated = 'na' | 'yes' | 'no';

export type Rating =
  'instrument' | 'multi_engine' | 'cfi' | 'cfii' | 'mei' | 'seaplane' | 'helicopter' | 'glider';

export type MedicalType = 'none' | 'basicmed' | 'first' | 'second' | 'third';

export interface Dart {
  id: number;
  name: string;
  airport_identifier: string;
  city: string;
}

export interface Plan {
  slug: string;
  name: string;
  price_cents: number;
  duration_days: number | null;
  description: string;
}

export interface Profile {
  /* contact */
  phone: string;
  phone_alt: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  county: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  /* aviation */
  home_airport_identifier: string;
  home_airport_city: string;
  dart: Pick<Dart, 'id' | 'name'> | null;
  air_care_alliance_number: string;
  pilot_certificate_type: PilotCertificateType;
  certificate_number: string;
  ifr_rated: IfrRated;
  ratings: Rating[];
  medical_type: MedicalType;
  medical_expiration: IsoDate | null;
  medical_is_current: boolean;
  flight_review_date: IsoDate | null;
  total_hours: number | null;
  aircraft: AircraftSummary[];
  /* volunteer interests */
  vol_ground_team: boolean;
  vol_exercise_training: boolean;
  vol_member_support: boolean;
  vol_fundraising: boolean;
  vol_social_media: boolean;
  vol_newsletter: boolean;
}

/** The writable half of a profile: `dart` reads nested, but writes as `dart_id`. */
export type ProfilePatch = Partial<
  Omit<Profile, 'dart' | 'aircraft' | 'medical_is_current'> & { dart_id: number | null }
>;

/** `POST /me/profile/aircraft` answers with the aircraft the profile now lists. */
export interface AttachedAircraft {
  aircraft: AircraftSummary[];
}

/** A row in the `account_admin` member list. */
export interface MemberRow {
  user_id: number;
  name: string;
  email: string;
  phone: string;
  dart: string | null;
  is_active: boolean;
  membership: MembershipStatus;
  pilot_certificate_type: PilotCertificateType;
  medical_type: MedicalType;
  medical_expiration: IsoDate | null;
  medical_is_current: boolean;
  aircraft: string[];
  joined_on: IsoDate | null;
}

/* ---------------------------------------------------- member administration */
/** The profile in `GET /admin/members/{id}`: the member's own, plus the notes. */
export interface AdminProfile extends Profile {
  notes: string;
  how_heard: string;
}

/**
 * One membership term in `GET /admin/members/{id}`, and the row that
 * `PATCH /admin/memberships/{id}` edits.
 */
export interface MemberTerm extends MembershipTerm {
  plan_slug: string;
  note: string;
  granted_by: string | null;
  payment: number | null;
  created_at: IsoDateTime;
}

/** One payment row in `GET /admin/members/{id}`: a `Payment` without the account it names. */
export type MemberPayment = Omit<Payment, 'user_id' | 'user_name'>;

/** `GET /admin/members/{id}`. */
export interface MemberDetail {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  name: string;
  is_active: boolean;
  roles: RoleSlug[];
  created_at: IsoDateTime;
  joined_on: IsoDate | null;
  membership: MembershipStatus;
  profile: AdminProfile | null;
  memberships: MemberTerm[];
  payments: MemberPayment[];
}

/** The nested `profile` of a member write: the member's patch, plus the notes. */
export type AdminProfilePayload = ProfilePatch & {
  notes?: string;
  how_heard?: string;
};

/** `POST /admin/members`. */
export interface MemberCreatePayload {
  email: string;
  first_name?: string;
  last_name?: string;
  password?: string;
  profile?: AdminProfilePayload;
}

/** `PATCH /admin/members/{id}`. */
export interface MemberUpdatePayload {
  email?: string;
  first_name?: string;
  last_name?: string;
  is_active?: boolean;
  profile?: AdminProfilePayload;
}

/** `POST /admin/members/{id}/memberships`. */
export interface GrantTermPayload {
  plan: string;
  starts_on?: IsoDate | null;
  note?: string;
}

/** `PATCH /admin/memberships/{id}`. */
export interface TermUpdatePayload {
  ends_on?: IsoDate | null;
  status?: MembershipTermStatus;
  note?: string;
}

/* ---------------------------------------------------------------- aircraft */
export type OwnerType = 'individual' | 'fbo' | 'club';

export interface AircraftSummary {
  id: number;
  n_number: string;
  make: string;
  model: string;
  insurance_is_current: boolean;
  insurance_expiration: IsoDate | null;
  insurance_summary: string;
}

export interface Aircraft extends AircraftSummary {
  year: number | null;
  owner_type: OwnerType;
  owner_name: string;
  owner_contact: string;
  seats: number | null;
  insurance_carrier: string;
  insurance_policy_number: string;
  insurance_liability_per_occurrence_cents: number;
  insurance_liability_per_person_cents: number;
  insurance_hull_cents: number | null;
  notes: string;
  created_by: number | null;
  is_active: boolean;
}

export type AircraftPatch = Partial<
  Omit<
    Aircraft,
    'id' | 'insurance_is_current' | 'insurance_summary' | 'created_by' | 'n_number'
  > & { n_number: string }
>;

/** A member who lists an aircraft among the planes they commonly fly. */
export interface AircraftPilot {
  user_id: number;
  name: string;
  email: string;
  membership_status: MembershipState;
  medical_is_current: boolean;
}

/**
 * `GET /aircraft/{id}`, `/aircraft/lookup` and `/leader/aircraft`.
 *
 * `pilots` names other members and reports their medical currency, so the
 * server only sends it to a `dart_leader` or `account_admin`; it is absent
 * for a plain member reading the register.
 */
export interface AircraftDetail extends Aircraft {
  pilots?: AircraftPilot[];
}

/* ---------------------------------------------------------------- payments */
export type PaymentProvider = 'stripe' | 'paypal' | 'mock';

export type PaymentWallet =
  'card' | 'apple_pay' | 'google_pay' | 'link' | 'paypal' | 'mock' | 'unknown';

export type PaymentState = 'pending' | 'succeeded' | 'failed' | 'refunded';

export interface Payment {
  id: number;
  user_id: number;
  user_name: string;
  plan: string | null;
  amount_cents: number;
  plan_amount_cents: number;
  contribution_cents: number;
  currency: string;
  provider: PaymentProvider;
  wallet: PaymentWallet;
  provider_ref: string;
  status: PaymentState;
  created_at: IsoDateTime;
  completed_at: IsoDateTime | null;
}

/** The trimmed row shown on `/me/payments`. */
export interface PaymentSummary {
  id: number;
  plan: string | null;
  amount_cents: number;
  contribution_cents: number;
  provider: PaymentProvider;
  status: PaymentState;
  completed_at: IsoDateTime | null;
}

export interface ContributionTier {
  label: string;
  cents: number;
}

export interface PaymentsConfig {
  providers: PaymentProvider[];
  stripe_publishable_key: string;
  paypal_client_id: string;
  plans: Plan[];
  contribution_tiers: ContributionTier[];
}

export interface CheckoutRequest {
  plan: string | null;
  contribution_cents: number;
  provider: PaymentProvider;
}

export type CheckoutResponse =
  | { payment_id: number; provider: 'stripe'; client: { client_secret: string } }
  | { payment_id: number; provider: 'paypal'; client: { order_id: string } }
  | { payment_id: number; provider: 'mock' };

export interface PaymentResult {
  status: PaymentState;
  membership: MembershipStatus;
}

/** One row of `GET /admin/payments/summary`. */
export interface PaymentPeriodSummary {
  period: string;
  count: number;
  total_cents: number;
  plan_cents: number;
  contribution_cents: number;
  by_provider: Partial<Record<PaymentProvider, number>>;
}

/* ------------------------------------------------------------------ leader */
export interface LeaderSearchResult {
  user_id: number;
  name: string;
  email: string;
  dart: string | null;
  membership_status: MembershipState;
}

export interface LeaderStatus {
  name: string;
  email: string;
  phone: string;
  dart: string | null;
  membership: {
    status: MembershipState;
    expires_on: IsoDate | null;
    plan: string | null;
  };
  certificate: {
    type: PilotCertificateType;
    number: string;
    ifr_rated: IfrRated;
    ratings: Rating[];
  };
  medical: {
    type: MedicalType;
    expiration: IsoDate | null;
    is_current: boolean;
  };
  aircraft: AircraftSummary[];
  go_no_go: {
    membership: boolean;
    medical: boolean;
  };
}

/* --------------------------------------------------------------- reminders */
export type ReminderKind = 't60' | 't30' | 't7' | 'expired' | 'post30';

export interface ReminderLogEntry {
  id: number;
  user_id: number;
  user_name: string;
  membership_id: number;
  kind: ReminderKind;
  sent_at: IsoDateTime;
  to_email: string;
}

export interface ReminderRunResult {
  sent: number;
  skipped: number;
}

/* ------------------------------------------------------------------ system */
export interface Health {
  db: string;
  pending_migrations: number;
  disk_free_mb: number;
  last_backup: IsoDateTime | null;
  version: string;
  debug: boolean;
}

export interface Backup {
  name: string;
  size_bytes: number;
  created_at: IsoDateTime;
}

/* -------------------------------------------------------------------- site */
/** A top-navigation entry is either a Wagtail page or a portal action. */
export type NavKind = 'page' | 'portal';

export interface NavEntry {
  title: string;
  url: string;
  active: boolean;
  kind: NavKind;
}

export interface MembersPage {
  title: string;
  url: string;
}

/** A theme slug shipped in `frontend/src/styles/themes/`. */
export type ThemeSlug = 'sierra' | 'pacific' | 'night';

export interface SiteConfig {
  org_name: string;
  theme: ThemeSlug;
  contact_email: string;
  nav: NavEntry[];
  members_pages: MembersPage[];
}

/* -------------------------------------------------------------- pagination */
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
