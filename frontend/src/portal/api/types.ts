/**
 * TypeScript shapes for every object in the API contract
 * (`docs/developer/api-reference.rst`).
 *
 * Features import from here rather than redeclaring shapes, so keep these in
 * step with the DRF serializers.  Dates are ISO-8601 strings
 * (`YYYY-MM-DD` for dates, full timestamps for datetimes).
 */
import type { ReportSlug } from '@/portal/reports/types';

export type IsoDate = string;
export type IsoDateTime = string;

export type RoleSlug =
  | 'member'
  | 'verifier'
  | 'dart_leader'
  | 'user_admin'
  | 'treasurer'
  | 'account_admin'
  | 'management'
  | 'website_admin'
  | 'system_admin';

export interface Role {
  slug: RoleSlug;
  description: string;
}

/* -------------------------------------------------------------- membership */
/**
 * A donor's membership reads `donor`; no screen draws it, since a donor cannot sign in.
 * `none` is an account that chose to be a member and holds no term yet, such as one an
 * administrator created that has not paid: *Not yet paid*, never *Friend*.
 */
export type MembershipState = 'current' | 'expired' | 'friend' | 'none' | 'donor';

export interface MembershipStatus {
  status: MembershipState;
  expires_on: IsoDate | null;
  plan: string | null;
  is_lifetime: boolean;
}

/** A `suspended` term belongs to an account its holder deactivated; it counts for nothing. */
export type MembershipTermStatus = 'active' | 'expired' | 'canceled' | 'suspended';
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
/** The kind of person an account belongs to: a member pays dues, a friend does not. */
export type AccountKind = 'member' | 'friend' | 'donor';

/** The kinds a person may choose, or an administrator set: never a donor. */
export type PersonKind = Exclude<AccountKind, 'donor'>;

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  roles: RoleSlug[];
  is_active: boolean;
  membership: MembershipStatus;
  profile_complete: boolean;
  /** False until the owner follows a link sent to the address they hold now. */
  email_verified: boolean;
  /** The kind as stored; a member with a `friend_on` date still reads `member` until then. */
  kind: AccountKind;
  /** The day a member who asked to become a friend becomes one, or null. */
  friend_on: IsoDate | null;
  /**
   * True for an account an account administrator created on New member: its owner has
   * joined already, so once the address is verified the portal skips the profile and
   * pay steps.
   */
  admin_created: boolean;
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
  /** `member` when left out. */
  kind?: PersonKind;
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

/** `POST /auth/email/verify`: the token from a verification link. */
export interface EmailVerifyPayload {
  token: string;
}

/** `POST /auth/email/verify`: the address the link verified. */
export interface EmailVerifyResult {
  email: string;
}

/** `POST /auth/email/change`: the address to move to, and the current password. */
export interface EmailChangePayload {
  email: string;
  current_password: string;
}

/** `POST /auth/deactivate`: the signed-in user's current password. */
export interface DeactivatePayload {
  current_password: string;
}

/**
 * `POST /me/kind/friend`: whether the automatic renewal's contribution carries on as a
 * yearly recurring donation.  Needed only when the renewal takes a contribution.
 */
export interface BecomeFriendPayload {
  keep_contribution?: boolean;
}

/** `POST /auth/email/resend` and `/admin/users/{id}/send-email-verification`. */
export interface VerificationSentResult {
  detail: string;
}

/* ------------------------------------------------------ user administration */
/**
 * `/admin/users`: the user payload, plus when the address was verified, when and why it
 * last bounced, and whether a user administrator has blocked the account from
 * reactivating.
 */
export interface AdminUser extends User {
  email_verified_at: IsoDateTime | null;
  /** When the bounce check last found the address bouncing; null with no bounce known. */
  email_bounced_at: IsoDateTime | null;
  /** That report's status code and diagnostic, or `''`. */
  email_bounce_detail: string;
  reactivation_blocked: boolean;
  /** Read from the profile, blank without one, for the columns the users list can show. */
  phone: string;
  /** The DART's name, or null without one. */
  dart: string | null;
  city: string;
  county: string;
  home_airport: string;
}

/** What one entry of an account's history did: `GET /admin/users/{id}/history`. */
export type AccountChangeKind =
  'created' | 'roles' | 'deactivated' | 'reactivated' | 'blocked' | 'unblocked';

/**
 * One row of `GET /admin/users/{id}/history`, newest first.  `changed_by` is null for a
 * management command (`by_command`) or an account since deleted; `added` and `removed` are the role
 * slugs a `roles` entry granted and took away, and empty for every other kind.
 */
export interface AccountChange {
  id: number;
  changed_at: IsoDateTime;
  changed_by: AccountActor | null;
  /** True for a change a management command made; false with no actor means one since deleted. */
  by_command: boolean;
  kind: AccountChangeKind;
  added: RoleSlug[];
  removed: RoleSlug[];
}

/** The account behind a history entry: its id and the name to print beside a date. */
export interface AccountActor {
  id: number;
  name: string;
}

/**
 * `GET|PATCH /admin/users/{id}` and the record's status actions: the list's row plus
 * what the record needs to word the membership as the member record does.
 */
export interface AdminUserDetail extends AdminUser {
  has_terms: boolean;
  has_suspended_term: boolean;
}

/**
 * The writable half of `PATCH /admin/users/{id}`. The active flag and the block are
 * changed through the record's own actions, never a patch.
 */
export interface AdminUserPatch {
  first_name?: string;
  last_name?: string;
  email?: string;
  roles?: RoleSlug[];
}

/** `POST /admin/users/{id}/send-password-reset`. */
export interface SendPasswordResetResult {
  detail: string;
}

/* ------------------------------------------------------------------ member */
export type PilotCertificateType =
  'none' | 'student' | 'sport' | 'recreational' | 'private' | 'commercial' | 'atp';

/**
 * A rating a member holds, in the two rows the forms show: the category and
 * class ratings, then the instructor ones.
 */
export type Rating =
  'asel' | 'amel' | 'ases' | 'ames' | 'helicopter' | 'instrument' | 'cfi' | 'cfii' | 'mei';

export type MedicalType = 'none' | 'basicmed' | 'first' | 'second' | 'third';

/* ------------------------------------------------------------ verification */
/** The kind of photo ID a verifier saw; nothing else about the document is recorded. */
export type PhotoIdType =
  'not_provided' | 'drivers_license' | 'passport' | 'state_id' | 'military_id' | 'other';

/** A person's verified item: the pilot certificate, the medical, or the photo ID. */
export type VerificationItem = 'certificate' | 'medical' | 'photo_id';

/**
 * One verified item's state.  `verified_by` is the verifier's display name and
 * `verified_at` the moment; both are `null` while the item is unverified.
 */
export interface Verification {
  verified: boolean;
  verified_by: string | null;
  verified_at: IsoDateTime | null;
}

/** The verified state of a person's three items, as a profile carries it. */
export interface ProfileVerification {
  certificate: Verification;
  medical: Verification;
  photo_id: Verification;
}

/**
 * `PUT /leader/members/{user_id}/verification`.  Each field is optional (an
 * omitted one is left alone); `verified` lists the items that end verified.
 */
export interface MemberVerificationPayload {
  pilot_certificate_type?: PilotCertificateType;
  certificate_number?: string;
  medical_type?: MedicalType;
  medical_expiration?: IsoDate | null;
  photo_id_type?: PhotoIdType;
  verified: VerificationItem[];
}

/** `PUT /leader/aircraft/{id}/verification`: the insurance fields and the verdict. */
export interface InsuranceVerificationPayload {
  insurance_carrier?: string;
  insurance_policy_number?: string;
  insurance_liability_per_occurrence_cents?: number;
  insurance_liability_per_person_cents?: number;
  insurance_hull_cents?: number | null;
  insurance_expiration?: IsoDate | null;
  verified: boolean;
}

/** `PUT /leader/members/{user_id}/verifier`: whether the member holds the role. */
export interface VerifierGrantPayload {
  verifier: boolean;
}

/** One named volunteer who runs a DART, and how to reach them. */
export interface DartContact {
  id?: number;
  name: string;
  title: string;
  phone: string;
  email: string;
}

export interface Dart {
  id: number;
  name: string;
  /** Every field the team flies from, as `"CCR, C83"`. */
  airport_identifiers: string;
  /** The team's own site, or `''` when it has none. */
  website_url: string;
  contacts: DartContact[];
}

/**
 * One person on a DART as the account administrator edits them.
 *
 * `receives_roster` says whether they are sent the team's roster; the public
 * catalog leaves it out.
 */
export interface AdminDartContact extends DartContact {
  receives_roster: boolean;
}

/**
 * A DART as the account administrator's screen works with it.
 *
 * `member_count` and `page_count` say what points at the DART: the members
 * whose profile names it, and the website pages linked to it.  Both are
 * read-only, and both being zero is what makes a DART deletable.
 * `roster_recipients` counts the people checked to receive the roster who have
 * an email address, and `roster_sent_at` is when the last roster went out, or
 * `null` when none has; both are read-only too.
 */
export interface AdminDart extends Omit<Dart, 'contacts'> {
  contacts: AdminDartContact[];
  is_active: boolean;
  member_count: number;
  page_count: number;
  roster_recipients: number;
  roster_sent_at: string | null;
}

/**
 * The body of `POST /admin/darts` and `PATCH /admin/darts/{id}`.
 *
 * `contacts` replaces the stored list; leaving it out keeps the list as it is.
 */
export type AdminDartPatch = Partial<
  Omit<AdminDart, 'id' | 'member_count' | 'page_count' | 'roster_recipients' | 'roster_sent_at'>
>;

export interface Plan {
  slug: string;
  name: string;
  price_cents: number;
  duration_days: number | null;
  description: string;
}

/** A two-letter US state or territory code, as the profile stores it. */
export type UsState =
  | 'AL'
  | 'AK'
  | 'AZ'
  | 'AR'
  | 'CA'
  | 'CO'
  | 'CT'
  | 'DE'
  | 'DC'
  | 'FL'
  | 'GA'
  | 'HI'
  | 'ID'
  | 'IL'
  | 'IN'
  | 'IA'
  | 'KS'
  | 'KY'
  | 'LA'
  | 'ME'
  | 'MD'
  | 'MA'
  | 'MI'
  | 'MN'
  | 'MS'
  | 'MO'
  | 'MT'
  | 'NE'
  | 'NV'
  | 'NH'
  | 'NJ'
  | 'NM'
  | 'NY'
  | 'NC'
  | 'ND'
  | 'OH'
  | 'OK'
  | 'OR'
  | 'PA'
  | 'RI'
  | 'SC'
  | 'SD'
  | 'TN'
  | 'TX'
  | 'UT'
  | 'VT'
  | 'VA'
  | 'WA'
  | 'WV'
  | 'WI'
  | 'WY'
  | 'AS'
  | 'GU'
  | 'MP'
  | 'PR'
  | 'VI';

/** A California county, which is the only county list the profile offers. */
export type CaliforniaCounty =
  | 'Alameda'
  | 'Alpine'
  | 'Amador'
  | 'Butte'
  | 'Calaveras'
  | 'Colusa'
  | 'Contra Costa'
  | 'Del Norte'
  | 'El Dorado'
  | 'Fresno'
  | 'Glenn'
  | 'Humboldt'
  | 'Imperial'
  | 'Inyo'
  | 'Kern'
  | 'Kings'
  | 'Lake'
  | 'Lassen'
  | 'Los Angeles'
  | 'Madera'
  | 'Marin'
  | 'Mariposa'
  | 'Mendocino'
  | 'Merced'
  | 'Modoc'
  | 'Mono'
  | 'Monterey'
  | 'Napa'
  | 'Nevada'
  | 'Orange'
  | 'Placer'
  | 'Plumas'
  | 'Riverside'
  | 'Sacramento'
  | 'San Benito'
  | 'San Bernardino'
  | 'San Diego'
  | 'San Francisco'
  | 'San Joaquin'
  | 'San Luis Obispo'
  | 'San Mateo'
  | 'Santa Barbara'
  | 'Santa Clara'
  | 'Santa Cruz'
  | 'Shasta'
  | 'Sierra'
  | 'Siskiyou'
  | 'Solano'
  | 'Sonoma'
  | 'Stanislaus'
  | 'Sutter'
  | 'Tehama'
  | 'Trinity'
  | 'Tulare'
  | 'Tuolumne'
  | 'Ventura'
  | 'Yolo'
  | 'Yuba';

export interface Profile {
  /** The account's names, edited here with the profile; never blank once saved. */
  first_name: string;
  last_name: string;
  /* contact */
  phone: string;
  phone_extension: string;
  phone_alt: string;
  phone_alt_extension: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: UsState;
  postal_code: string;
  county: CaliforniaCounty | '';
  emergency_contact_name: string;
  emergency_contact_phone: string;
  emergency_contact_phone_extension: string;
  /** A US amateur radio callsign, upper case, or blank. */
  ham_callsign: string;
  /** The day they first joined, stamped with their first term and never moved. */
  member_since: IsoDate | null;
  /* aviation */
  home_airport_identifier: string;
  secondary_airport_identifier: string;
  dart: Pick<Dart, 'id' | 'name'> | null;
  air_care_alliance_number: string;
  pilot_certificate_type: PilotCertificateType;
  certificate_number: string;
  ratings: Rating[];
  medical_type: MedicalType;
  medical_expiration: IsoDate | null;
  medical_is_current: boolean;
  flight_review_date: IsoDate | null;
  total_hours: number | null;
  photo_id_type: PhotoIdType;
  /** Read-only: only the member check's verification endpoint verifies an item. */
  verification: ProfileVerification;
  aircraft: AircraftSummary[];
  flies_rented_aircraft: boolean;
  /* volunteer interests */
  vol_mission_pilot: boolean;
  vol_ground_team: boolean;
  vol_exercise_training: boolean;
  vol_member_support: boolean;
  vol_fundraising: boolean;
  vol_social_media: boolean;
  vol_newsletter: boolean;
}

/** The account's names, which `/me/profile` carries and the member record keeps apart. */
export type ProfileNameKey = 'first_name' | 'last_name';

/** The writable half of a profile: `dart` reads nested, but writes as `dart_id`. */
export type ProfilePatch = Partial<
  Omit<Profile, 'dart' | 'aircraft' | 'medical_is_current' | 'member_since' | 'verification'> & {
    dart_id: number | null;
  }
>;

/** `POST /me/profile/aircraft` answers with the aircraft the profile now lists. */
export interface AttachedAircraft {
  aircraft: AircraftSummary[];
}

/**
 * One address `GET /addresses/suggest` offers for the street line typed so far:
 * the whole address on one line, and the five profile fields a pick fills.
 * `state` is a two-letter code and `county` one of California's, each empty when
 * the provider named none the profile stores.
 */
export interface AddressSuggestion {
  label: string;
  address_line1: string;
  city: string;
  state: string;
  postal_code: string;
  county: string;
}

/** A row in the `account_admin` member list. */
export interface MemberRow {
  user_id: number;
  name: string;
  email: string;
  phone: string;
  dart: string | null;
  is_active: boolean;
  kind: AccountKind;
  membership: MembershipStatus;
  pilot_certificate_type: PilotCertificateType;
  medical_type: MedicalType;
  medical_expiration: IsoDate | null;
  medical_is_current: boolean;
  aircraft: string[];
  joined_on: IsoDate | null;
  profile_updated_at: IsoDateTime | null;
  certificate_number: string;
  /** Whether a pilot holds an instrument rating; null for somebody who is no pilot. */
  instrument: boolean | null;
  home_airport: string;
  secondary_airport: string;
  city: string;
  state: string;
  county: string;
  ham_callsign: string;
  member_since: IsoDate | null;
}

/* ---------------------------------------------------- member administration */
/**
 * The profile in `GET /admin/members/{id}`: the member's own, plus the notes.  The
 * names are the member record's account fields, so the nested profile leaves them out.
 */
export interface AdminProfile extends Omit<Profile, ProfileNameKey> {
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

/** One payment row in `GET /admin/members/{id}`: the member's own money, no finance detail. */
export interface MemberPayment {
  id: number;
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

/** `GET /admin/members/{id}`. */
export interface MemberDetail {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  name: string;
  is_active: boolean;
  /** Set by a user administrator: the account stays deactivated until it is lifted. */
  reactivation_blocked: boolean;
  kind: AccountKind;
  /** True for a "Deleted member N" account, which keeps a deleted account's payments. */
  is_tombstone: boolean;
  /** The day a member who is to become a friend becomes one; null when none is pending. */
  friend_on: IsoDate | null;
  roles: RoleSlug[];
  created_at: IsoDateTime;
  email_verified_at: IsoDateTime | null;
  /** When the bounce check last found the address bouncing; null with no bounce known. */
  email_bounced_at: IsoDateTime | null;
  /** That report's status code and diagnostic, or `''`. */
  email_bounce_detail: string;
  joined_on: IsoDate | null;
  profile_updated_at: IsoDateTime | null;
  membership: MembershipStatus;
  profile: AdminProfile | null;
  memberships: MemberTerm[];
  payments: MemberPayment[];
}

/** The nested `profile` of a member write: the member's patch, plus the notes. */
export type AdminProfilePayload = Omit<ProfilePatch, ProfileNameKey> & {
  notes?: string;
  how_heard?: string;
  /** Read-only for a member; an administrator may correct the joining date. */
  member_since?: IsoDate | null;
};

/** `POST /admin/members`. */
export interface MemberCreatePayload {
  email: string;
  first_name?: string;
  last_name?: string;
  password?: string;
  /** `member` when left out; an administrator never creates a donor. */
  kind?: PersonKind;
  profile?: AdminProfilePayload;
}

/** `PATCH /admin/members/{id}`. The Delete or deactivate tab deactivates and reactivates. */
export interface MemberUpdatePayload {
  email?: string;
  first_name?: string;
  last_name?: string;
  /** Makes the account that kind at once; refused for a donor. */
  kind?: PersonKind;
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

/** What kind of aircraft an airframe is, as the FAA registry classes it. */
export type AircraftCategory =
  | 'airplane'
  | 'helicopter'
  | 'gyroplane'
  | 'glider'
  | 'balloon'
  | 'airship'
  | 'powered_lift'
  | 'weight_shift'
  | 'powered_parachute'
  | 'other';

/** The classification of an airframe's airworthiness certificate. */
export type Airworthiness =
  | 'standard'
  | 'limited'
  | 'restricted'
  | 'experimental'
  | 'provisional'
  | 'multiple'
  | 'primary'
  | 'special_flight_permit'
  | 'light_sport';

/**
 * Whether the coverage policy excludes an aircraft.  `reason` is blank when there
 * is nothing to say, `Category not recorded` for an aircraft with no category the
 * policy does not otherwise exclude, and `Not covered: …` for an excluded one.
 */
export interface AircraftCoverage {
  excluded: boolean;
  reason: string;
}

/**
 * `GET`/`PUT /aircraft/coverage-policy`: the aircraft categories and airworthiness
 * classifications CalDART's insurance does not cover, and the note members read.
 */
export interface AircraftCoveragePolicy {
  excluded_categories: AircraftCategory[];
  excluded_airworthiness: Airworthiness[];
  note: string;
}

/**
 * One entry of the aircraft types, from `GET /aircraft/types?q=`.
 *
 * `seats` and `engines` are null when the registry does not say; `is_custom`
 * marks a type an account administrator added by hand.
 */
export interface AircraftType {
  id: number;
  make: string;
  model: string;
  seats: number | null;
  engines: number | null;
  /** Blank when the registry does not say, as for a hand-added type. */
  category: AircraftCategory | '';
  is_custom: boolean;
}

/**
 * The body of `POST /aircraft/types` (account administrators): a type the FAA has
 * never registered.  The make and model come back as display names.
 */
export interface AircraftTypeCreatePayload {
  make: string;
  model: string;
  seats?: number | null;
  engines?: number | null;
}

/** Who holds an FAA registration, as the registry codes it. */
export type RegistrantType =
  | 'individual'
  | 'partnership'
  | 'corporation'
  | 'co_owned'
  | 'government'
  | 'llc'
  | 'non_citizen_corporation'
  | 'non_citizen_co_owned'
  | 'unknown';

/** Whether an FAA registration stands. */
export type RegistrationStatus = 'valid' | 'pending' | 'revoked' | 'expired' | 'other';

/** One N-number as the FAA registry holds it, from `GET /aircraft/registry/{n_number}`. */
export interface Registration {
  n_number: string;
  type: AircraftType;
  year: number | null;
  registrant_name: string;
  registrant_type: RegistrantType;
  status: RegistrationStatus;
  certificate_issued_on: IsoDate | null;
  expires_on: IsoDate | null;
  /** Blank when the registry records no airworthiness certificate. */
  airworthiness: Airworthiness | '';
  imported_at: IsoDateTime;
}

/** One run of the FAA registry import; `finished_at` is null while it runs. */
export interface RegistryImport {
  started_at: IsoDateTime;
  finished_at: IsoDateTime | null;
  ok: boolean;
  error: string;
  types_written: number;
  registrations_written: number;
  types_folded: number;
  source: string;
}

/**
 * `GET /aircraft/registry`: when the newest successful import finished (`as_of`),
 * whether one is running, and the newest run of any outcome.
 */
export interface RegistryStatus {
  as_of: IsoDateTime | null;
  running: boolean;
  last: RegistryImport | null;
}

/** `make` and `model` are the display names of `type`, repeated for convenience. */
export interface AircraftSummary {
  id: number;
  n_number: string;
  make: string;
  model: string;
  type: AircraftType;
  /** Blank until somebody records it. */
  category: AircraftCategory | '';
  /** Blank until somebody records it. */
  airworthiness: Airworthiness | '';
  coverage: AircraftCoverage;
  insurance_is_current: boolean;
  insurance_expiration: IsoDate | null;
  /** Each liability limit in cents; 0 when none is recorded. */
  insurance_liability_per_occurrence_cents: number;
  insurance_liability_per_person_cents: number;
  insurance_summary: string;
  insurance_verified: boolean;
  /** The account that added the record, or null. */
  created_by: number | null;
}

/** The register record; its insurance state is `insurance_verification` rather than a flag. */
export interface Aircraft extends Omit<AircraftSummary, 'insurance_verified'> {
  year: number | null;
  /** When the register record was last written, by anybody. */
  updated_at: IsoDateTime;
  owner_type: OwnerType;
  owner_name: string;
  owner_contact: string;
  seats: number | null;
  insurance_carrier: string;
  insurance_policy_number: string;
  insurance_liability_per_occurrence_cents: number;
  insurance_liability_per_person_cents: number;
  insurance_hull_cents: number | null;
  insurance_verification: Verification;
  notes: string;
  created_by: number | null;
  is_active: boolean;
}

/**
 * The write body of `POST /aircraft` and `PATCH /aircraft/{id}`.  The type is
 * written as `type_id`; `make`, `model`, `type`, and `coverage` are read-only.
 */
export type AircraftPatch = Partial<
  Omit<
    Aircraft,
    | 'id'
    | 'make'
    | 'model'
    | 'type'
    | 'coverage'
    | 'insurance_is_current'
    | 'insurance_summary'
    | 'insurance_verified'
    | 'insurance_verification'
    | 'created_by'
    | 'updated_at'
    | 'n_number'
  > & { n_number: string; type_id: number }
>;

/** A member who lists an aircraft among the planes they commonly fly. */
export interface AircraftPilot {
  user_id: number;
  name: string;
  email: string;
  membership_status: MembershipState;
  medical_is_current: boolean;
  /** The member check's verdict for this person, so both checks give one answer. */
  go_no_go: LeaderGoNoGo;
}

/** The account behind a write: its id and the name to print beside the date. */
export interface AircraftActor {
  id: number;
  name: string;
}

/** What kind of write an entry of an aircraft's history records. */
export type AircraftChangeKind = 'created' | 'updated';

/**
 * One row of `GET /aircraft/{id}/changes`.
 *
 * `fields` names the columns the write moved, and is empty on a `created`
 * entry, where the whole record is the change.
 */
export interface AircraftChange {
  id: number;
  changed_at: IsoDateTime;
  changed_by: AircraftActor | null;
  kind: AircraftChangeKind;
  fields: string[];
}

/**
 * `GET /aircraft/{id}`, `/aircraft/lookup` and `/leader/aircraft`.
 *
 * `pilots` names other members and reports their medical currency, so the
 * server only sends it to a `dart_leader` or `account_admin`; it is absent
 * for a plain member reading the register.  `updated_by` names another member
 * too, and is sent on the same terms.
 */
export interface AircraftDetail extends Aircraft {
  updated_by?: AircraftActor | null;
  pilots?: AircraftPilot[];
}

/* ---------------------------------------------------------------- payments */
export type PaymentProvider = 'stripe' | 'paypal' | 'mock' | 'manual';

export type PaymentWallet =
  | 'card'
  | 'apple_pay'
  | 'google_pay'
  | 'link'
  | 'paypal'
  | 'mock'
  | 'check'
  | 'cash'
  | 'bank_transfer'
  | 'other'
  | 'unknown';

export type PaymentState = 'pending' | 'succeeded' | 'failed' | 'partially_refunded' | 'refunded';

/** What a payment bought: dues, a contribution, or both at once. */
export type PaymentKind = 'membership' | 'contribution' | 'both';

/** The membership term a payment bought, as the finance row carries it. */
export interface FinancePaymentTerm {
  id: number;
  starts_on: IsoDate;
  ends_on: IsoDate | null;
  status: MembershipTermStatus;
}

/** The automatic charge a payment came from, when it came from one. */
export interface PaymentRenewalAttempt {
  id: number;
  scheduled_on: IsoDate;
  outcome: RenewalOutcome;
}

/** One row of `GET /admin/payments`: the finance view of one payment. */
export interface Payment {
  id: number;
  user_id: number;
  user_name: string;
  user_email: string;
  /** True when the payer is a "Deleted member N" account, whose record cannot be changed. */
  user_is_tombstone: boolean;
  plan: string | null;
  kind: PaymentKind;
  amount_cents: number;
  plan_amount_cents: number;
  contribution_cents: number;
  fee_cents: number;
  net_cents: number;
  refunded_cents: number;
  currency: string;
  provider: PaymentProvider;
  wallet: PaymentWallet;
  provider_ref: string;
  status: PaymentState;
  receipt_number: string;
  receipt_sent_at: IsoDateTime | null;
  /** The day the money counts as received: `received_on` for a check, else the completion. */
  paid_on: IsoDate | null;
  received_on: IsoDate | null;
  reconciled_on: IsoDate | null;
  reconciled_by: string | null;
  recorded_by: string | null;
  note: string;
  membership: FinancePaymentTerm | null;
  renewal_attempt: PaymentRenewalAttempt | null;
  created_at: IsoDateTime;
  completed_at: IsoDateTime | null;
}

/** `GET /admin/payments/{id}`: the finance row with its refunds beneath it. */
export interface PaymentDetail extends Payment {
  refunds: Refund[];
}

/** The membership term one payment bought, as its own payment row names it. */
export interface PaymentTerm {
  id: number;
  starts_on: IsoDate;
  ends_on: IsoDate | null;
}

/** The row shown on `/me/payments`: everything the payments screen draws. */
export interface PaymentSummary {
  id: number;
  plan: string | null;
  kind: PaymentKind;
  amount_cents: number;
  plan_amount_cents: number;
  contribution_cents: number;
  refunded_cents: number;
  provider: PaymentProvider;
  wallet: PaymentWallet;
  status: PaymentState;
  /** The ledger date: the day a check arrived, or the day the provider settled. */
  paid_on: IsoDate | null;
  completed_at: IsoDateTime | null;
  receipt_sent_at: IsoDateTime | null;
  membership: PaymentTerm | null;
}

/** `GET /me/payments/statements` -- the years a statement can be had for. */
export interface StatementYears {
  years: number[];
}

/** `POST /admin/payments/{id}/receipt` -- what came of sending the receipt again. */
export interface ReceiptSend {
  sent: boolean;
  receipt_sent_at: IsoDateTime | null;
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
  /** The largest contribution checkout accepts, in cents. */
  max_contribution_cents: number;
}

export interface CheckoutRequest {
  plan: string | null;
  contribution_cents: number;
  provider: PaymentProvider;
  /**
   * Save the method and charge it again on a schedule.  With a plan, the membership
   * renews each year; with none, the contribution is a recurring donation.  Defaults
   * to false.
   */
  auto_renew?: boolean;
  /**
   * The day the saved method first charges on. Null takes the new term's expiry for a
   * renewal, and one cadence after today for a donation.
   */
  next_charge_on?: IsoDate | null;
  /** How often a recurring donation charges. A renewal takes only `yearly`, the default. */
  cadence?: MandateCadence;
  /** Move the renewal's contribution to this donation. Defaults to false. */
  remove_renewal_contribution?: boolean;
}

export type CheckoutResponse =
  | { payment_id: number; provider: 'stripe'; client: { client_secret: string } }
  | { payment_id: number; provider: 'paypal'; client: { order_id: string } }
  | { payment_id: number; provider: 'mock'; client: Record<string, never> };

export interface PaymentResult {
  status: PaymentState;
  membership: MembershipStatus;
}

/* ---------------------------------------------------------- public donations */
/** One state the public donation form offers: its two-letter code and its name. */
export interface StateChoice {
  value: string;
  label: string;
}

/** `GET /donations/config`: everything the public donation form offers. */
export interface DonationsConfig {
  providers: PaymentProvider[];
  stripe_publishable_key: string;
  paypal_client_id: string;
  contribution_tiers: ContributionTier[];
  /** The largest gift the checkout accepts, in cents. */
  max_contribution_cents: number;
  counties: string[];
  darts: Pick<Dart, 'id' | 'name'>[];
  states: StateChoice[];
}

/**
 * `POST /donations/checkout`: who is giving, how much, and through which provider.
 *
 * The four names and addresses are required; the rest are the donor's profile, each
 * left out when the giver left it blank.
 */
export interface DonationCheckoutRequest {
  first_name: string;
  last_name: string;
  email: string;
  /** Optional, as on every profile. */
  phone?: string;
  contribution_cents: number;
  provider: PaymentProvider;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: UsState | '';
  postal_code?: string;
  county?: CaliforniaCounty | '';
  home_airport_identifier?: string;
  dart_id?: number | null;
  air_care_alliance_number?: string;
  pilot_certificate_type?: PilotCertificateType;
  vol_mission_pilot?: boolean;
  vol_ground_team?: boolean;
  vol_exercise_training?: boolean;
  vol_member_support?: boolean;
  vol_fundraising?: boolean;
  vol_social_media?: boolean;
  vol_newsletter?: boolean;
}

/** The 201 of `POST /donations/checkout`: the portal checkout's answer, plus the token. */
export type DonationCheckoutResponse = CheckoutResponse & { token: string };

/* ----------------------------------------------------------------- refunds */
export type RefundReason = 'requested_by_member' | 'duplicate' | 'error' | 'fraudulent' | 'other';

export type RefundState = 'pending' | 'succeeded' | 'failed';

/** One refund against a payment, in whole or in part. */
export interface Refund {
  id: number;
  payment_id: number;
  amount_cents: number;
  reason: RefundReason;
  note: string;
  status: RefundState;
  /** The Stripe or PayPal refund id; empty for a manual or mock refund. */
  provider_ref: string;
  /** Null when the refund was issued in the provider's own dashboard. */
  requested_by_id: number | null;
  refunded_at: IsoDateTime | null;
  created_at: IsoDateTime;
}

/** The body of `POST /admin/payments/{id}/refunds`. */
export interface RefundRequest {
  amount_cents: number;
  reason: RefundReason;
  note?: string;
  /** Cancel the membership term the payment bought. */
  cancel_term?: boolean;
}

/** A payment as it stands after a refund. */
export interface RefundedPayment {
  id: number;
  amount_cents: number;
  refunded_cents: number;
  status: PaymentState;
}

/** The 201 body of `POST /admin/payments/{id}/refunds`. */
export interface RefundIssued {
  refund: Refund;
  payment: RefundedPayment;
}

/** One row of `GET /admin/payments/summary`. */
export interface PaymentPeriodSummary {
  period: string;
  count: number;
  total_cents: number;
  plan_cents: number;
  contribution_cents: number;
  fee_cents: number;
  net_cents: number;
  refunded_cents: number;
  by_provider: Partial<Record<PaymentProvider, number>>;
}

/* -------------------------------------------------------- automatic renewal */
/** The providers that can charge a saved payment method again. */
export type MandateProvider = 'stripe' | 'paypal' | 'mock';

export type MandateStatus = 'pending' | 'active' | 'paused' | 'canceled';

export type RenewalOutcome = 'scheduled' | 'succeeded' | 'failed' | 'skipped';

/**
 * What a standing authority charges for. `contribution` is a recurring donation, which
 * renews nothing; `both` is an automatic renewal with a contribution beside the dues.
 */
export type MandateKind = 'renewal' | 'both' | 'contribution';

/** How often a standing authority charges. An automatic renewal is always `yearly`. */
export type MandateCadence = 'monthly' | 'quarterly' | 'yearly';

/**
 * One person's standing authority for CalDART to charge them on a schedule: an
 * automatic renewal, which names a plan, or a recurring donation, which names none.
 */
export interface RenewalMandate {
  id: number;
  user_id: number;
  user_name: string;
  user_email: string;
  /** The slug of the plan that renews, or null for a recurring donation. */
  plan: string | null;
  plan_name: string | null;
  /** A renewal, a recurring donation (`contribution`), or a renewal with a contribution. */
  kind: MandateKind;
  cadence: MandateCadence;
  contribution_cents: number;
  /** The plan's price plus the contribution: what the next charge comes to. */
  amount_cents: number;
  provider: MandateProvider;
  method_label: string;
  method_brand: string;
  method_last4: string;
  method_exp_month: number | null;
  method_exp_year: number | null;
  status: MandateStatus;
  failure_count: number;
  /** The day of the next charge: the stored day, or a waiting charge's own. Null
   * only for a mandate that is not active. */
  next_charge_on: IsoDate | null;
  /** Why the most recent charge was refused, or an empty string. */
  last_error: string;
  last_charged_at: IsoDateTime | null;
  canceled_at: IsoDateTime | null;
  created_at: IsoDateTime;
}

/** `GET | PATCH /me/renewal` and `/me/donation`: `mandate` is null when there is none. */
export interface RenewalEnvelope {
  mandate: RenewalMandate | null;
}

/** One scheduled renewal charge, as `GET /admin/renewals/attempts` lists it. */
export interface RenewalAttempt {
  id: number;
  mandate_id: number;
  /** The term the charge renews; null for a recurring donation. */
  membership_id: number | null;
  payment_id: number | null;
  user_id: number;
  user_name: string;
  scheduled_on: IsoDate;
  outcome: RenewalOutcome;
  error: string;
  noticed_at: IsoDateTime | null;
  attempted_at: IsoDateTime | null;
  result_emailed_at: IsoDateTime | null;
  created_at: IsoDateTime;
}

/** `POST /me/renewal/setup` and `POST /me/donation/setup`. */
export interface RenewalSetupRequest {
  /** The plan to renew, which a renewal needs. A donation leaves it out. */
  plan?: string;
  contribution_cents: number;
  provider: MandateProvider;
  /**
   * The day of the first charge. Null takes the day the membership runs out for a
   * renewal, and today for a donation.
   */
  next_charge_on?: IsoDate | null;
  /** How often a donation charges. A renewal takes only `yearly`, the default. */
  cadence?: MandateCadence;
  /** Move the renewal's contribution to this donation. Defaults to false. */
  remove_renewal_contribution?: boolean;
}

/** `PATCH /me/renewal` and `/me/donation`: what the authority charges, how often, when. */
export interface RenewalPatchRequest {
  /** Leaving it out leaves the plan alone. A donation does not read it. */
  plan?: string;
  contribution_cents: number;
  /** Moves the next charge. Null leaves the stored day alone. */
  next_charge_on?: IsoDate | null;
  /** How often a donation charges. Null leaves it alone; a renewal takes only `yearly`. */
  cadence?: MandateCadence | null;
}

export type RenewalSetupResponse =
  | { provider: 'stripe'; client: { client_secret: string } }
  | { provider: 'paypal'; client: { setup_token: string } }
  | { provider: 'mock'; client: Record<string, never> };

export interface RenewalConfirmRequest {
  setup_intent_id: string;
  setup_token: string;
}

/**
 * One email a scan sent or would send, or one charge it took, and who it was about.
 *
 * `kind` is the email template name, a reminder kind, or `charge`. `on` is the
 * date the action concerns and `amount_cents` the money a charge moves; both are
 * null for an action that carries neither.
 */
export interface RunAction {
  kind: string;
  member: string;
  email: string;
  on: IsoDate | null;
  amount_cents: number | null;
  detail: string;
}

/** The counts one automatic-renewal scan reports, and who they were about. */
export interface RenewalRunResult {
  noticed: number;
  warned: number;
  charged: number;
  failed: number;
  paused: number;
  skipped: number;
  actions: RunAction[];
}

/* ------------------------------------------------------------------ finance */
/** How money taken by hand was presented. */
export type ManualMethod = 'check' | 'cash' | 'bank_transfer' | 'other';

/** One row of `GET /admin/payments/reconciliation`: a period, or a provider. */
export interface ReconciliationRow {
  period: string;
  count: number;
  gross_cents: number;
  fee_cents: number;
  net_cents: number;
  refunded_cents: number;
  net_after_refunds_cents: number;
  reconciled_count: number;
  unreconciled_count: number;
}

/** One row of `GET /admin/payments/contributions`: a member's giving for one year. */
export interface ContributionRow {
  user_id: number;
  name: string;
  email: string;
  count: number;
  contribution_cents: number;
  refunded_cents: number;
  net_contribution_cents: number;
}

/** One row of `GET /admin/payments/donors`: one donor's giving over the reported range. */
export interface DonorRow {
  user_id: number;
  name: string;
  email: string;
  phone: string;
  city: string;
  state: string;
  county: string;
  dart: string;
  first_gift: IsoDate | null;
  last_gift: IsoDate | null;
  gifts: number;
  given_cents: number;
  refunded_cents: number;
  net_cents: number;
  active: boolean;
  /** True for the "Deleted member N" row of a deleted account's gifts. */
  is_tombstone: boolean;
}

/** The counts one year-end statement run reports, and who they were about. */
export interface StatementsRunResult {
  year: number;
  sent: number;
  skipped: number;
  failed: number;
  actions: RunAction[];
}

/** One row of `GET /admin/payments/members`: a member a payment can be recorded for. */
export interface FinanceMember {
  user_id: number;
  name: string;
  email: string;
  membership: MembershipStatus;
}

/** Who a ledger is about. */
export interface LedgerMember {
  id: number;
  name: string;
  email: string;
  /** True for a "Deleted member N" account, which keeps a deleted account's payments. */
  is_tombstone: boolean;
  membership: MembershipStatus;
}

/** What a member has paid over their whole history, in cents. */
export interface LedgerTotals {
  paid_cents: number;
  contribution_cents: number;
  fee_cents: number;
  refunded_cents: number;
}

/** `GET /admin/payments/ledger/{user_id}`. */
export interface MemberLedger {
  user: LedgerMember;
  totals: LedgerTotals;
  payments: PaymentDetail[];
  mandate: RenewalMandate | null;
  statement_years: number[];
}

/** `PATCH /admin/payments/{id}`: the two fields a treasurer writes. */
export interface PaymentPatch {
  reconciled_on?: IsoDate | null;
  note?: string;
}

/** `POST /admin/payments/record`: money taken by check, cash or transfer. */
export interface ManualPaymentPayload {
  user_id: number;
  plan: string | null;
  contribution_cents: number;
  method: ManualMethod;
  reference: string;
  received_on: IsoDate;
  note: string;
}

/* ------------------------------------------------------------------ leader */
/** The medical on file, as both the search results and the status card carry it. */
export interface LeaderMedical {
  type: MedicalType;
  expiration: IsoDate | null;
  is_current: boolean;
  verification: Verification;
}

/** The kind of photo ID on file, and its verification. */
export interface LeaderPhotoId {
  type: PhotoIdType;
  verification: Verification;
}

/**
 * Why a member is a go or a no-go, rather than only whether they are.
 * `verified` is true when the certificate, the medical, and the photo ID are all verified.
 */
export interface LeaderGoNoGo {
  membership: boolean;
  medical: boolean;
  verified: boolean;
}

export interface LeaderSearchResult {
  user_id: number;
  name: string;
  dart: string | null;
  membership_status: MembershipState;
  go_no_go: LeaderGoNoGo;
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
    ratings: Rating[];
    verification: Verification;
  };
  medical: LeaderMedical;
  photo_id: LeaderPhotoId;
  is_dart_leader: boolean;
  is_verifier: boolean;
  aircraft: AircraftSummary[];
  go_no_go: LeaderGoNoGo;
}

/* --------------------------------------------------------------- email log */
export type EmailStatus = 'sent' | 'failed' | 'bounced';

/**
 * One email the system tried to send, as `GET /system/emails` returns it.
 *
 * `purpose` is the template's name and `purpose_label` the words a reader sees
 * for it, the name itself when the server has no label for the template.
 * `bounced_at` and `bounce_detail` are set only on a `bounced` row: when the bounce
 * check read the report, and its status code and diagnostic.
 */
export interface EmailLogEntry {
  id: number;
  to_email: string;
  user_id: number | null;
  user_name: string;
  purpose: string;
  purpose_label: string;
  subject: string;
  sent_at: IsoDateTime;
  status: EmailStatus;
  error: string;
  attachments: string;
  bounced_at: IsoDateTime | null;
  bounce_detail: string;
  /** The portal page the message belongs to, such as `/bulk-email/sent/9`; blank for none. */
  link: string;
}

/**
 * What one bounce check found, from `POST /system/bounces/run`. `enabled` is false
 * when no bounce mailbox is configured. `skipped` counts the messages left unread: one
 * the mail server would not hand over, or one too large to be a report. Each action's
 * `kind` is `bounced` or `unmatched`, and its `detail` the report's status code and
 * diagnostic.
 */
export interface BounceRunResult {
  enabled: boolean;
  bounced: number;
  unmatched: number;
  ignored: number;
  skipped: number;
  actions: RunAction[];
}

/** Whether bounce checking is set up, from `GET /system/bounces`. */
export interface BounceStatus {
  enabled: boolean;
}

/** A role an email type may name as one that sends it. */
export type EmailTypeSenderRole = 'dart_leader' | 'management';

/**
 * A type of bulk email, from `GET /email-types` (system administrators only).
 * `slug` follows `name`. `sender_roles` lists the roles that may send the type, once
 * each in the order above; an empty list leaves it to system administrators.
 * `allow_opt_out` says whether a recipient may turn it off. `position` orders the
 * types on every screen, then `name`. `in_use` is true once a bulk email has the type,
 * which then cannot be deleted.
 */
export interface EmailType {
  id: number;
  name: string;
  slug: string;
  description: string;
  allow_opt_out: boolean;
  sender_roles: EmailTypeSenderRole[];
  position: number;
  in_use: boolean;
}

/**
 * The body of `POST /email-types` and `PUT /email-types/{id}`. Without `position` a
 * new type goes after every other and an edited one keeps its place.
 */
export interface EmailTypeInput {
  name: string;
  description: string;
  allow_opt_out: boolean;
  sender_roles: EmailTypeSenderRole[];
  position?: number;
}

/**
 * A type the caller may send, from `GET /email-types/sendable`. `is_mission` is true
 * for the Mission type, the only one a mission callout offers.
 */
export interface SendableEmailType {
  id: number;
  name: string;
  description: string;
  allow_opt_out: boolean;
  is_mission: boolean;
}

/**
 * One type a person may turn off, and whether they have, from `GET
 * /me/email-preferences` or `GET /admin/members/{id}/email-preferences`.
 * `email_type` is the type's id. Types nobody may turn off are not listed. For a type
 * turned off, `opted_out_source` says where and `opted_out_at` when; `''` and null for
 * a type left on.
 */
export interface EmailPreference {
  email_type: number;
  name: string;
  description: string;
  opted_out: boolean;
  opted_out_source: OptOutSource | '';
  opted_out_at: IsoDateTime | null;
}

/** Where an opt-out was recorded: Email preferences, an unsubscribe link, or an administrator. */
export type OptOutSource = 'profile' | 'unsubscribe' | 'admin';

/** One entry of the list a `PUT` of email preferences takes. */
export interface EmailPreferenceChange {
  email_type: number;
  opted_out: boolean;
}

/** One purpose the email log's filter offers, from `GET /system/emails/purposes`. */
export interface EmailPurpose {
  value: string;
  label: string;
}

/* --------------------------------------------------------------- reminders */
export type ReminderKind = 'first' | 'second' | 'final' | 'expired' | 'lapsed';

export interface ReminderLogEntry {
  id: number;
  user_id: number;
  user_name: string;
  membership_id: number;
  kind: ReminderKind;
  sent_at: IsoDateTime;
  to_email: string;
}

/**
 * What one reminder scan did.
 *
 * `skipped_by_reason` carries one entry per reason a candidate was passed over,
 * so a run that sent little can say why, and `failed` counts the sends the mail
 * server refused.
 */
export interface ReminderRunResult {
  sent: number;
  skipped: number;
  failed: number;
  skipped_by_reason: Record<string, number>;
  actions: RunAction[];
}

/**
 * The body of `PUT /admin/reminders/schedule` (system administrators): whole days
 * before expiry for the first, second, and final reminders, and after it for the
 * lapsed one.
 */
export interface ReminderSchedulePayload {
  first_days_before: number;
  second_days_before: number;
  final_days_before: number;
  lapsed_days_after: number;
}

/**
 * `GET /admin/reminders/schedule`: when each reminder stage falls, and who saved the
 * schedule last and when. Both are null while the defaults (60, 30, 7, 30) apply.
 */
export interface ReminderSchedule extends ReminderSchedulePayload {
  updated_by: string | null;
  updated_at: IsoDateTime | null;
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

/** How one line of the mail delivery check turned out. */
export type MailDeliveryStatus = 'pass' | 'warn' | 'fail';

/**
 * One line of `GET /mail/delivery-check`: `detail` says what the record is for and what
 * was found, and `fix` what to ask for (blank when `status` is `pass`).
 */
export interface MailDeliveryFinding {
  name: string;
  status: MailDeliveryStatus;
  detail: string;
  fix: string;
}

/**
 * `GET /mail/delivery-check`: the domain of the site's From address (blank when it has
 * none), when the lookups were made, and one finding per line.
 */
export interface MailDeliveryCheck {
  domain: string;
  checked_at: IsoDateTime;
  findings: MailDeliveryFinding[];
}

export interface Backup {
  name: string;
  size_bytes: number;
  created_at: IsoDateTime;
}

/* -------------------------------------------------------------------- site */
/** A top-navigation entry is either a Wagtail page or a portal action. */
export type NavKind = 'page' | 'portal';

/** One entry of a navigation drop-down. */
export interface NavChild {
  title: string;
  url: string;
}

export interface NavEntry {
  title: string;
  url: string;
  active: boolean;
  kind: NavKind;
  children: NavChild[];
}

export interface MembersPage {
  title: string;
  url: string;
}

/** A theme slug shipped in `frontend/src/styles/themes/`. */
export type ThemeSlug =
  | 'duty'
  | 'sierra'
  | 'pacific'
  | 'night'
  | 'squadron'
  | 'flight-deck'
  | 'contrail'
  | 'sectional'
  | 'tarmac'
  | 'coastal'
  | 'slate'
  | 'meridian'
  | 'monterey-night'
  | 'granite';

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

/* ------------------------------------------------------------------ reports */
/** One entry of `GET /reports`: a report the caller may download. */
export interface ReportSummary {
  slug: string;
  title: string;
  /** Whether `?columns=` may choose the report's columns. */
  choosable: boolean;
  /** Whether the report takes `?period=`. */
  periods: boolean;
}

/** One entry of `GET /reports/{slug}/columns`, which drives the column chooser. */
export interface ReportColumn {
  key: string;
  label: string;
  default: boolean;
}

/** One saved set of a report's columns, from `/reports/{slug}/column-sets`. */
export interface SavedColumnSet {
  id: number;
  name: string;
  /** Column keys, in the order the report prints them. */
  columns: string[];
}

/** The body of `POST /reports/{slug}/column-sets`: save, or replace the set of that name. */
export interface SavedColumnSetWrite {
  name: string;
  columns: string[];
}

/** How often a report subscription is sent. */
export type ReportCadence = 'weekly' | 'monthly' | 'quarterly' | 'yearly';

/** Which files a report subscription attaches: one format, or `both`. */
export type ReportFormats = 'csv' | 'pdf' | 'both';

/**
 * One report emailed to one address on a schedule, from `/reports/subscriptions`.
 *
 * `recipient_user` is the bound account, or null for an address outside CalDART,
 * whose `recipient_name` is then blank. `filters` are the report's own params
 * (`period` included) and `columns` the chosen keys, empty for the defaults.
 * `weekday` (0 Monday to 6 Sunday) is read by the `weekly` cadence alone.
 */
export interface ReportSubscription {
  id: number;
  report: string;
  report_title: string;
  recipient_user: number | null;
  recipient_name: string;
  recipient_email: string;
  filters: Record<string, string>;
  columns: string[];
  formats: ReportFormats;
  cadence: ReportCadence;
  weekday: number;
  is_active: boolean;
  created_by_name: string;
  last_sent_at: IsoDateTime | null;
  next_due_on: IsoDate;
}

/**
 * The body of `POST /reports/subscriptions`. `confirmed` must be true when no
 * account holds `recipient_email`.
 */
export interface ReportSubscriptionCreate {
  report: ReportSlug;
  recipient_email: string;
  filters?: Record<string, string>;
  columns?: string[];
  formats: ReportFormats;
  cadence: ReportCadence;
  weekday?: number;
  confirmed?: boolean;
}

/** The fields `PATCH /reports/subscriptions/{id}` may change. */
export type ReportSubscriptionPatch = Partial<
  Pick<ReportSubscription, 'is_active' | 'filters' | 'columns' | 'formats' | 'cadence' | 'weekday'>
>;

/** One active DART's roster, from `GET /reports/rosters`. */
export interface Roster {
  dart_id: number;
  name: string;
  /** How many people checked to receive the roster have an email address. */
  roster_recipients: number;
  roster_sent_at: IsoDateTime | null;
}

/**
 * What one run of the report sender did, or would do: the three run endpoints'
 * answer. Each action is kind `report` (the report and formats in `detail`) or
 * `roster` (the DART in `detail`).
 */
export interface ReportRunResult {
  sent: number;
  skipped: number;
  failed: number;
  skipped_by_reason: Record<string, number>;
  actions: RunAction[];
}

/* ------------------------------------------------------------ notifications */

/**
 * One event an address may subscribe to, from `GET /notifications/events`, in
 * catalog order. `category` is the heading the screen groups it under, and
 * `roles` the role slugs whose holders may receive it (a system administrator
 * always may).
 */
export interface NotificationEvent {
  slug: string;
  label: string;
  category: string;
  description: string;
  roles: string[];
}

/**
 * One notification subscription: an address and the event slugs it is sent,
 * in catalog order. `recipient_user` is the bound account, or null for an
 * address outside CalDART, whose `recipient_name` is then blank.
 */
export interface NotificationSubscription {
  id: number;
  recipient_user: number | null;
  recipient_name: string;
  recipient_email: string;
  events: string[];
  is_active: boolean;
  created_by_name: string;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

/**
 * The body of `POST /notifications/subscriptions`. `confirmed` must be true
 * when no account holds `recipient_email`.
 */
export interface NotificationSubscriptionCreate {
  recipient_email: string;
  events: string[];
  confirmed?: boolean;
}

/** The fields `PATCH /notifications/subscriptions/{id}` may change. */
export type NotificationSubscriptionPatch = Partial<
  Pick<NotificationSubscription, 'events' | 'is_active'>
>;

/* --------------------------------------------------------------- bulk email */

/**
 * Where a bulk email stands: a `draft` and a `queued` email (waiting for its
 * start time) can still change; `sending` is the background sender at work, and
 * `sent` and `stopped` are the two ways it ends.
 */
export type BulkEmailStatus = 'draft' | 'queued' | 'sending' | 'sent' | 'stopped';

/**
 * Where one person's copy stands. `batched` is a row of an email not yet started;
 * starting the send makes each `pending` or `skipped`, and each pending row then
 * becomes `sent`, `failed`, or `stopped`. `bounced` is a copy that came back.
 */
export type BulkEmailRecipientStatus =
  'batched' | 'pending' | 'sent' | 'failed' | 'skipped' | 'stopped' | 'bounced';

/**
 * One bulk email, from `GET /bulk-email/{id}`: the message, where it stands, its
 * batch counts, and its progress. `sender` and `stopped_by` are display names,
 * blank when there is none. `remaining` counts the copies waiting to go, and
 * `estimated_finish_at` is set while it is sending. `confirm_above` is the batch
 * size above which Send asks for the count to be typed, and `undo_seconds` the
 * undo window the countdown runs over. `body` is the message as sanitized HTML,
 * and `message_html` the whole HTML email with its field tokens as written.
 * `email_type` is the chosen type's id, null while none is chosen, and
 * `email_type_name` its name, blank then. `not_sent_reason` says why the background
 * sender returned the email unsent, and is blank otherwise. `dart_name` is the DART a
 * DART leader's email goes to, blank for CalDART management's. `sender_notice` says why
 * nobody can be added to the email, naming its sender, while that sender's profile names
 * no DART; it is blank otherwise.
 * `reply_to` is where replies go, blank for `default_reply_to`; once the email is
 * queued it is the address its copies carry. `bounced_count` counts the
 * copies the bounce check later found refused, which `sent_count` no longer counts;
 * `retries` lists each press of Retry failed, oldest first, and `retried_count` adds
 * up the copies they queued again. `hidden_from_archive` is true while the email is
 * kept off the recipients' Messages page. `is_callout` is true for a mission callout,
 * whose answers close at `closes_at`, null for any other email.
 */
export interface BulkEmailDetail {
  id: number;
  subject: string;
  body: string;
  email_type: number | null;
  email_type_name: string;
  not_sent_reason: string;
  reply_to: string;
  default_reply_to: string;
  status: BulkEmailStatus;
  sender: string;
  sender_id: number | null;
  dart_name: string;
  sender_notice: string;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  start_at: IsoDateTime | null;
  scheduled: boolean;
  confirm_count: number | null;
  started_at: IsoDateTime | null;
  sent_at: IsoDateTime | null;
  stopped_at: IsoDateTime | null;
  stopped_by: string;
  stop_requested: boolean;
  sent_count: number;
  failed_count: number;
  skipped_count: number;
  bounced_count: number;
  retried_count: number;
  retries: BulkEmailRetry[];
  hidden_from_archive: boolean;
  is_callout: boolean;
  closes_at: IsoDateTime | null;
  can_edit: boolean;
  batch_count: number;
  receiving_count: number;
  batch_skipped_count: number;
  remaining: number;
  estimated_finish_at: IsoDateTime | null;
  confirm_above: number;
  undo_seconds: number;
  message_html: string;
}

/** One press of Retry failed: when, by whom (blank once that account is gone), and how many. */
export interface BulkEmailRetry {
  id: number;
  requested_at: IsoDateTime;
  requested_by: string;
  count: number;
}

/**
 * One person's copy as it went, from `GET /bulk-email/{id}/recipients/{rid}/copy`:
 * who it went to, its result, and the copy filled in with the values stored when it
 * was sent. `html` is the whole HTML email and `text` the plain-text one.
 */
export interface BulkEmailCopy {
  id: number;
  name: string;
  email: string;
  status: BulkEmailRecipientStatus;
  tried_at: IsoDateTime;
  subject: string;
  html: string;
  text: string;
}

/** The body of `POST /bulk-email/{id}/hide`: true to hide it from Messages, false to show it. */
export interface BulkEmailHideRequest {
  hidden: boolean;
}

/**
 * One bulk email the signed-in person received, from `GET /messages`: the subject as
 * their copy had it, when it went to them, who sent it (the organization's name once
 * the sender's account is gone), and its type, blank for none. `answer_url` is the
 * reader's own answer page for a mission callout, blank for any other email.
 */
export interface BulkEmailMessage {
  id: number;
  subject: string;
  sent_at: IsoDateTime;
  from_name: string;
  email_type_name: string;
  answer_url: string;
}

/**
 * One message as the reader received it, from `GET /messages/{id}`: the list's fields
 * and the reader's own copy, `html` and `text`, as it went.
 */
export interface BulkEmailMessageDetail extends BulkEmailMessage {
  html: string;
  text: string;
}

/**
 * One row of `GET /bulk-email/drafts` or `GET /bulk-email/sent`. `email_type_name` is
 * blank while no type is chosen; `not_sent_reason` says why the background sender
 * returned the email unsent, blank otherwise. `dart_name` is the DART a DART leader's
 * email goes to, blank for CalDART management's.
 */
export interface BulkEmailSummary {
  id: number;
  subject: string;
  email_type_name: string;
  not_sent_reason: string;
  status: BulkEmailStatus;
  sender: string;
  dart_name: string;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
  start_at: IsoDateTime | null;
  scheduled: boolean;
  started_at: IsoDateTime | null;
  sent_at: IsoDateTime | null;
  stopped_at: IsoDateTime | null;
  stop_requested: boolean;
  sent_count: number;
  failed_count: number;
  skipped_count: number;
  batch_count: number;
  remaining: number;
}

/**
 * `GET /bulk-email/sender`: who the signed-in sender may send to. CalDART management
 * sends to everyone (`is_management`); a DART leader to `dart`, the DART on their
 * profile. `can_send` is false when there is nobody to send to, and `reason` says why.
 * `default_reply_to` is where replies go when the sender chooses no Reply-To address.
 */
export interface BulkEmailSender {
  is_management: boolean;
  can_send: boolean;
  reason: string;
  dart: number | null;
  dart_name: string;
  default_reply_to: string;
}

/** The fields `PATCH /bulk-email/{id}` may change. */
export interface BulkEmailPatch {
  subject?: string;
  body?: string;
  /** The id of a type the sender may send (`GET /email-types/sendable`). */
  email_type?: number;
  /** Where replies go: a valid address, or blank for the default. */
  reply_to?: string;
  /** True to make the email a mission callout, false to make it an ordinary email. */
  is_callout?: boolean;
  /** When a callout's answers close: a site-time `YYYY-MM-DDTHH:MM`. */
  closes_at?: string;
}

/**
 * The body of `POST /bulk-email/{id}/send`: the count the sender typed, and the
 * time to start, a site-time `YYYY-MM-DDTHH:MM` or null to start after the undo window.
 */
export interface BulkEmailSendRequest {
  confirm_count?: number | null;
  start_at?: string | null;
}

/** The body of `POST /bulk-email/{id}/batch/add`: the member list filters to add by. */
export interface BulkEmailAddRequest {
  filters?: Record<string, string>;
}

/** What one add did: who joined, who was there already, and the batch's size. */
export interface BulkEmailAddResult {
  added: number;
  already_present: number;
  count: number;
}

/**
 * One add to the batch: its name (its filters in words, or `Group: <name>` and
 * `Copied from "<subject>"` for an add made otherwise), its filters as given, and its
 * counts. `group` is the saved group it brought in, null for any other add and once
 * that group is deleted.
 */
export interface BulkEmailBatchAdd {
  id: number;
  label: string;
  filters: Record<string, string>;
  group: number | null;
  added_count: number;
  already_count: number;
  created_at: IsoDateTime;
}

/**
 * One person a search on the compose screen matches, before anybody is added:
 * `will_receive` and `reason` say whether a copy would go and why not.
 */
export interface BulkEmailMatch {
  user_id: number;
  name: string;
  email: string;
  kind: string;
  dart_name: string;
  will_receive: boolean;
  reason: string;
}

/**
 * One person in the batch. `added_by` is the id of the add that brought them in;
 * `will_receive` and `reason` say whether a copy goes and why not.
 */
export interface BulkEmailBatchRow {
  id: number;
  user_id: number | null;
  name: string;
  email: string;
  kind: string;
  dart_name: string;
  added_by: number | null;
  status: BulkEmailRecipientStatus;
  will_receive: boolean;
  reason: string;
  tried_at: IsoDateTime | null;
}

/** `GET /bulk-email/{id}/batch`: the counts, the adds, and every person. */
export interface BulkEmailBatch {
  count: number;
  receiving: number;
  skipped: number;
  adds: BulkEmailBatchAdd[];
  rows: BulkEmailBatchRow[];
}

/**
 * What one run of the bulk email sender did, from `POST /system/bulk-email/run`.
 * `busy` is true when another run was working and this one did nothing;
 * `out_of_time` is true when the run's time ran out with `remaining` copies left
 * for the next run.
 */
export interface BulkEmailRunResult {
  busy: boolean;
  emails: number;
  sent: number;
  failed: number;
  skipped: number;
  out_of_time: boolean;
  remaining: number;
  actions: RunAction[];
}

/* ------------------------------------------------- bulk email: rich text */

/**
 * One recipient field from `GET /bulk-email/fields`: the `token` a message writes
 * in braces, `{first_name}`, the menu's `label`, and a `description` of what it holds.
 */
export interface BulkEmailField {
  token: string;
  label: string;
  description: string;
}

/**
 * One image stored by `POST /bulk-email/images`: `url` is absolute, the address
 * every copy links to, and `width` and `height` are its stored size in pixels.
 */
export interface BulkEmailImage {
  id: number;
  url: string;
  width: number;
  height: number;
}

/* ---------------------------------------------- bulk email: checks and tests */

/** How much a finding matters: an `error` stops the send, a `warning` does not. */
export type BulkEmailFindingLevel = 'error' | 'warning';

/**
 * One finding of `POST /bulk-email/{id}/checks`: a `code` the screen may key on,
 * its `level`, and a `message` for the sender to read.
 */
export interface BulkEmailFinding {
  code: string;
  level: BulkEmailFindingLevel;
  message: string;
}

/** The 400 of a send or a test the checks found errors in: the errors under `checks`. */
export interface BulkEmailChecksRefusal {
  checks: BulkEmailFinding[];
}

/** `POST /bulk-email/{id}/test`'s answer: the address the test copy went to. */
export interface BulkEmailTestResult {
  to: string;
}

/** The body of `POST /bulk-email/{id}/preview`: the batch row to preview, null for the first. */
export interface BulkEmailPreviewRequest {
  recipient_id?: number | null;
}

/** Whose copy a preview is: the batch row, null for the sender's own, and the person. */
export interface BulkEmailPreviewRecipient {
  id: number | null;
  name: string;
  email: string;
}

/**
 * `POST /bulk-email/{id}/preview`'s answer: one person's copy, filled in. `html` is
 * the whole HTML email and `text` the plain-text one. `position` is the person's
 * place, from 1, among the `count` who receive a copy (0 for the sender's own), and
 * `previous_id` and `next_id` the rows either side.
 */
export interface BulkEmailPreview {
  subject: string;
  html: string;
  text: string;
  recipient: BulkEmailPreviewRecipient;
  position: number;
  count: number;
  previous_id: number | null;
  next_id: number | null;
}

/* ------------------------------------------- bulk email: templates and groups */

/**
 * One saved template from `/bulk-email/templates`: a message a draft can start from.
 * `email_type` is null and `email_type_name` blank for none; `reply_to` is blank for
 * the default. `created_by` is who saved it, blank once that account is gone.
 */
export interface EmailTemplate {
  id: number;
  name: string;
  subject: string;
  body: string;
  email_type: number | null;
  email_type_name: string;
  reply_to: string;
  created_by: string;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

/** The body of `POST /bulk-email/templates`: the name, and the message to keep. */
export interface EmailTemplateWrite {
  name: string;
  subject?: string;
  body?: string;
  email_type?: number | null;
  reply_to?: string;
}

/** The body of `PATCH /bulk-email/templates/{id}`: the fields to change. */
export type EmailTemplatePatch = Partial<EmailTemplateWrite>;

/** The body of `POST /bulk-email/{id}/apply-template`: the template to fill the draft from. */
export interface ApplyTemplateRequest {
  template: number;
}

/** The body of `POST /bulk-email/{id}/duplicate`: whether the batch is copied too. */
export interface DuplicateRequest {
  copy_recipients?: boolean;
}

/**
 * How a saved recipient group holds its people: `fixed`, a list of accounts, or
 * `live`, a list of filter sets run afresh on each use.
 */
export type RecipientGroupKind = 'fixed' | 'live';

/**
 * One filter set of a live group: its filters in words and as given. `needs_fixing`
 * is true when the member list no longer accepts the set as stored.
 */
export interface RecipientGroupFilter {
  id: number;
  label: string;
  filters: Record<string, string>;
  position: number;
  needs_fixing: boolean;
}

/**
 * One saved recipient group from `/bulk-email/groups`. `count` is how many people it
 * holds now, null when `needs_fixing`: a live group with a stored filter set the member
 * list no longer accepts. `filter_sets` are a live group's, empty for a fixed one.
 * `created_by` is who made it, blank once that account is gone.
 */
export interface RecipientGroup {
  id: number;
  name: string;
  kind: RecipientGroupKind;
  count: number | null;
  needs_fixing: boolean;
  filter_sets: RecipientGroupFilter[];
  created_by: string;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

/** The body of `POST /bulk-email/groups`: an empty group's name and kind. */
export interface RecipientGroupWrite {
  name: string;
  kind: RecipientGroupKind;
}

/** The body of `PATCH /bulk-email/groups/{id}`: a group's name; its kind never changes. */
export type RecipientGroupPatch = Partial<RecipientGroupWrite>;

/**
 * One person in a group now. `kind` is `member` or `friend`; `is_active` is false
 * for a deactivated account, which a send skips.
 */
export interface GroupPerson {
  user_id: number;
  name: string;
  email: string;
  kind: string;
  dart_name: string;
  is_active: boolean;
}

/** `GET /bulk-email/groups/{id}/members`: how many people a group holds now, and each. */
export interface GroupPeople {
  count: number;
  people: GroupPerson[];
}

/** One member or friend from `GET /bulk-email/groups/people`, to add to a fixed group. */
export interface PersonMatch {
  id: number;
  name: string;
  email: string;
}

/** The body of `POST /bulk-email/groups/{id}/members`: the account to add. */
export interface GroupMemberAddRequest {
  user: number;
}

/** The body of `POST /bulk-email/groups/{id}/filters`: one set of member list filters. */
export interface GroupFilterAddRequest {
  filters?: Record<string, string>;
}

/** The body of `POST /bulk-email/{id}/batch/add-group`: the group to add. */
export interface AddGroupRequest {
  group: number;
}

/**
 * The body of `POST /bulk-email/{id}/save-group`: the group's name and kind, and the
 * search it keeps, the member list filters the compose screen shows.
 */
export interface SaveGroupRequest {
  name: string;
  kind: RecipientGroupKind;
  filters: Record<string, string>;
}

/* ----------------------------------------------------------- mission callouts */

/** What a recipient answered a mission callout. */
export type CalloutAnswerKind = 'available' | 'limited' | 'unavailable';

/** How many people a callout reached, and how many gave each answer or none. */
export interface CalloutCounts {
  reached: number;
  available: number;
  limited: number;
  unavailable: number;
  no_answer: number;
}

/** One round of Remind non-responders: its number, when, and the reminders it queued. */
export interface CalloutReminder {
  round: number;
  requested_at: IsoDateTime;
  count: number;
}

/**
 * One person a callout reached, from `GET /bulk-email/callouts/{id}`: their answer
 * (null before they give one), its note and time, and what the member check shows of
 * them now: DART, home airport, aircraft N-numbers, and the go/no-go verdicts.
 */
export interface CalloutRecipient {
  user_id: number;
  name: string;
  email: string;
  answer: CalloutAnswerKind | null;
  note: string;
  answered_at: IsoDateTime | null;
  dart_name: string;
  home_airport: string;
  aircraft: string[];
  go_no_go: LeaderGoNoGo;
}

/**
 * One callout, from `GET /bulk-email/callouts`. `sender` is blank once the account is
 * gone and `dart_name` blank for CalDART management's callout. `closes_at` is when
 * answers close, `closed_at` when Close now closed it sooner, and `is_open` whether
 * it takes answers now.
 */
export interface CalloutSummary {
  id: number;
  subject: string;
  status: BulkEmailStatus;
  sender: string;
  dart_name: string;
  started_at: IsoDateTime | null;
  sent_at: IsoDateTime | null;
  closes_at: IsoDateTime;
  closed_at: IsoDateTime | null;
  is_open: boolean;
  counts: CalloutCounts;
}

/**
 * One callout with its answers, from `GET /bulk-email/callouts/{id}`: who closed it
 * (blank when nobody did), how many copies were not sent because it had closed, each
 * round of reminders, and one row per person reached.
 */
export interface CalloutDetail extends CalloutSummary {
  closed_by: string;
  closed_skipped: number;
  reminders: CalloutReminder[];
  recipients: CalloutRecipient[];
}
