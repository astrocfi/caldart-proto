/**
 * Shapes the members-admin screens use on top of `api/types.ts` (PLAN §6.4).
 *
 * `MemberRow` (the list row) is already declared in the shared types; the
 * detail record, its nested profile and the write payloads are specific to
 * this feature and live here.
 */
import type {
  AircraftSummary,
  IsoDate,
  IsoDateTime,
  MedicalType,
  MembershipSource,
  MembershipStatus,
  MembershipTermStatus,
  PaymentProvider,
  PaymentState,
  PaymentWallet,
  PilotCertificateType,
  Rating,
  RoleSlug,
} from '../../api/types';

/** The profile as an administrator sees it: every field, notes included. */
export interface AdminProfile {
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
  home_airport_identifier: string;
  home_airport_city: string;
  dart: { id: number; name: string } | null;
  air_care_alliance_number: string;
  pilot_certificate_type: PilotCertificateType;
  certificate_number: string;
  ifr_rated: 'na' | 'yes' | 'no';
  ratings: Rating[];
  medical_type: MedicalType;
  medical_expiration: IsoDate | null;
  medical_is_current: boolean;
  flight_review_date: IsoDate | null;
  total_hours: number | null;
  aircraft: AircraftSummary[];
  vol_ground_team: boolean;
  vol_exercise_training: boolean;
  vol_member_support: boolean;
  vol_fundraising: boolean;
  vol_social_media: boolean;
  vol_newsletter: boolean;
  notes: string;
  how_heard: string;
}

/** One membership term in the history table. */
export interface MemberTerm {
  id: number;
  plan: string;
  plan_slug: string;
  starts_on: IsoDate;
  ends_on: IsoDate | null;
  status: MembershipTermStatus;
  source: MembershipSource;
  note: string;
  granted_by: string | null;
  payment: number | null;
  created_at: IsoDateTime;
}

/** One payment row on a member record. */
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
  roles: RoleSlug[];
  created_at: IsoDateTime;
  joined_on: IsoDate | null;
  membership: MembershipStatus;
  profile: AdminProfile | null;
  memberships: MemberTerm[];
  payments: MemberPayment[];
}

/** Profile fields as the API accepts them (`dart` becomes an id). */
export interface AdminProfilePayload {
  phone?: string;
  phone_alt?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  county?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  home_airport_identifier?: string;
  home_airport_city?: string;
  dart?: number | null;
  air_care_alliance_number?: string;
  pilot_certificate_type?: PilotCertificateType;
  certificate_number?: string;
  ifr_rated?: 'na' | 'yes' | 'no';
  ratings?: Rating[];
  medical_type?: MedicalType;
  medical_expiration?: IsoDate | null;
  flight_review_date?: IsoDate | null;
  total_hours?: number | null;
  vol_ground_team?: boolean;
  vol_exercise_training?: boolean;
  vol_member_support?: boolean;
  vol_fundraising?: boolean;
  vol_social_media?: boolean;
  vol_newsletter?: boolean;
  notes?: string;
  how_heard?: string;
}

export interface MemberCreatePayload {
  email: string;
  first_name?: string;
  last_name?: string;
  password?: string;
  profile?: AdminProfilePayload;
}

export interface MemberUpdatePayload {
  email?: string;
  first_name?: string;
  last_name?: string;
  is_active?: boolean;
  profile?: AdminProfilePayload;
}

export interface GrantTermPayload {
  plan: string;
  starts_on?: IsoDate | null;
  note?: string;
}

export interface TermUpdatePayload {
  ends_on?: IsoDate | null;
  status?: MembershipTermStatus;
  note?: string;
}

/** The list's query parameters (PLAN §6.4), all as strings for the URL. */
export interface MemberFilters {
  search: string;
  status: string;
  certificate: string;
  medical: string;
  dart: string;
  role: string;
  expiring_within: string;
  ordering: string;
}

export const EMPTY_FILTERS: MemberFilters = {
  search: '',
  status: '',
  certificate: '',
  medical: '',
  dart: '',
  role: '',
  expiring_within: '',
  ordering: '',
};

export const FILTER_KEYS = Object.keys(EMPTY_FILTERS) as (keyof MemberFilters)[];
