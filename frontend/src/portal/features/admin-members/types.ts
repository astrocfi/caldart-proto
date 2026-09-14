/**
 * Shapes the members-admin screens use on top of `api/types.ts`.
 *
 * `MemberRow` (the list row), `Profile` and `ProfilePatch` are already declared
 * in the shared types; an administrator's view of a profile is the member's
 * with two extra fields, so it is declared as exactly that.  The detail record
 * and the write payloads are specific to this feature and live here.
 */
import type {
  IsoDate,
  IsoDateTime,
  MembershipSource,
  MembershipStatus,
  MembershipTermStatus,
  PaymentProvider,
  PaymentState,
  PaymentWallet,
  Profile,
  ProfilePatch,
  RoleSlug,
} from '../../api/types';

/** The profile as an administrator sees it: the member's own, plus the notes. */
export interface AdminProfile extends Profile {
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

/** Profile fields as the API accepts them: the member's patch, plus the notes. */
export type AdminProfilePayload = ProfilePatch & {
  notes?: string;
  how_heard?: string;
};

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

/** The list's query parameters, all as strings for the URL. */
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
