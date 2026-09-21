/**
 * The frontend half of the API contract.
 *
 * `schema.d.ts` is generated from the backend's OpenAPI description by
 * `npm run schema`.  Every pair below ties one interface in `types.ts` to the
 * component the DRF serializers produce; the `Matches` assertions fail
 * `tsc --noEmit` the moment the two drift apart, and the runtime test fails
 * when a component disappears from the schema altogether.
 *
 * The comparison ignores `readonly` and optionality: OpenAPI marks a field
 * optional whenever the serializer does not require it on input, which says
 * nothing about whether the response carries it.  Property names and property
 * types are what the two sides must agree on.
 */

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import type { components } from './schema';
import type {
  Aircraft,
  AircraftPatch,
  AircraftSummary,
  AdminProfile,
  AdminProfilePayload,
  AdminUserPatch,
  Dart,
  IfrRated,
  MedicalType,
  MemberCreatePayload,
  MemberDetail,
  MemberPayment,
  MemberRow,
  MemberTerm,
  MemberUpdatePayload,
  MembershipSource,
  MembershipState,
  MembershipStatus,
  MembershipTermStatus,
  OwnerType,
  Paginated,
  Payment,
  PaymentProvider,
  PaymentResult,
  PaymentState,
  PaymentWallet,
  PilotCertificateType,
  Plan,
  Profile,
  ProfilePatch,
  Rating,
  ReminderKind,
  ReminderLogEntry,
  RoleSlug,
  TermUpdatePayload,
  User,
} from './types';

type Schemas = components['schemas'];

/**
 * Strip `readonly` and optionality, at every depth, so only property names and
 * value types are compared.  Nested objects and array elements carry the same
 * modifiers, so normalizing only the outermost level would report a difference
 * wherever one side nests another component.
 */
type Fields<T> = T extends readonly (infer Element)[]
  ? Fields<Element>[]
  : T extends object
    ? { -readonly [K in keyof T]-?: Fields<T[K]> }
    : T;

/** `true` only when the two types are mutually assignable. */
type IsExact<A, B> =
  (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2 ? true : false;

/** `true` only when the interface and its schema component describe the same object. */
type Matches<Ours, Theirs> = IsExact<Fields<Ours>, Fields<Theirs>>;

/* ------------------------------------------------------------------ enums */
const roleSlug: Matches<RoleSlug, Schemas['RolesEnum']> = true;
const membershipState: Matches<MembershipState, Schemas['MembershipStatusStatusEnum']> = true;
const termStatus: Matches<MembershipTermStatus, Schemas['AdminMembershipStatusEnum']> = true;
const membershipSource: Matches<MembershipSource, Schemas['SourceEnum']> = true;
const certificateType: Matches<PilotCertificateType, Schemas['PilotCertificateTypeEnum']> = true;
const ifrRated: Matches<IfrRated, Schemas['IfrRatedEnum']> = true;
const rating: Matches<Rating, Schemas['RatingsEnum']> = true;
const medicalType: Matches<MedicalType, Schemas['MedicalTypeEnum']> = true;
const ownerType: Matches<OwnerType, Schemas['OwnerTypeEnum']> = true;
const paymentProvider: Matches<PaymentProvider, Schemas['ProviderEnum']> = true;
const paymentWallet: Matches<PaymentWallet, Schemas['WalletEnum']> = true;
const paymentState: Matches<PaymentState, Schemas['PaymentStatusEnum']> = true;
const reminderKind: Matches<ReminderKind, Schemas['KindEnum']> = true;

/* ---------------------------------------------------------------- objects */
const membershipStatus: Matches<MembershipStatus, Schemas['MembershipStatus']> = true;
const dart: Matches<Dart, Schemas['Dart']> = true;
const plan: Matches<Plan, Schemas['Plan']> = true;
const profile: Matches<Profile, Schemas['Profile']> = true;
const profilePatch: Matches<ProfilePatch, Schemas['PatchedProfileRequest']> = true;
const adminProfile: Matches<AdminProfile, Schemas['AdminProfile']> = true;
const adminProfilePayload: Matches<AdminProfilePayload, Schemas['PatchedAdminProfileRequest']> =
  true;
const adminUserPatch: Matches<AdminUserPatch, Schemas['PatchedAdminUserRequest']> = true;
const memberRow: Matches<MemberRow, Schemas['MemberList']> = true;
const memberDetail: Matches<MemberDetail, Schemas['MemberDetail']> = true;
const memberTerm: Matches<MemberTerm, Schemas['AdminMembership']> = true;
const memberCreate: Matches<MemberCreatePayload, Schemas['MemberCreateRequest']> = true;
const memberUpdate: Matches<MemberUpdatePayload, Schemas['PatchedMemberUpdateRequest']> = true;
const termUpdate: Matches<TermUpdatePayload, Schemas['PatchedAdminMembershipRequest']> = true;
const aircraftSummary: Matches<AircraftSummary, Schemas['AircraftSummary']> = true;
const aircraft: Matches<Aircraft, Schemas['Aircraft']> = true;
const aircraftPatch: Matches<AircraftPatch, Schemas['PatchedAircraftRequest']> = true;
const user: Matches<User, Schemas['AdminUser']> = true;
const payment: Matches<Payment, Schemas['Payment']> = true;
const memberPayment: Matches<MemberPayment, Schemas['AdminPayment']> = true;
const paymentResult: Matches<PaymentResult, Schemas['PaymentResult']> = true;
const reminderLog: Matches<ReminderLogEntry, Schemas['ReminderLog']> = true;
const paginatedPayments: Matches<Paginated<Payment>, Schemas['PaginatedPaymentList']> = true;
const paginatedUsers: Matches<Paginated<User>, Schemas['PaginatedAdminUserList']> = true;
const paginatedMembers: Matches<Paginated<MemberRow>, Schemas['PaginatedMemberListList']> = true;
const paginatedAircraft: Matches<Paginated<Aircraft>, Schemas['PaginatedAircraftList']> = true;
const paginatedReminders: Matches<
  Paginated<ReminderLogEntry>,
  Schemas['PaginatedReminderLogList']
> = true;

/** Every pair above, so `noUnusedLocals` keeps each assertion referenced. */
const assertions: readonly true[] = [
  roleSlug,
  membershipState,
  termStatus,
  membershipSource,
  certificateType,
  ifrRated,
  rating,
  medicalType,
  ownerType,
  paymentProvider,
  paymentWallet,
  paymentState,
  reminderKind,
  membershipStatus,
  dart,
  plan,
  profile,
  profilePatch,
  adminProfile,
  adminProfilePayload,
  adminUserPatch,
  memberRow,
  memberDetail,
  memberTerm,
  memberCreate,
  memberUpdate,
  termUpdate,
  aircraftSummary,
  aircraft,
  aircraftPatch,
  user,
  payment,
  memberPayment,
  paymentResult,
  reminderLog,
  paginatedPayments,
  paginatedUsers,
  paginatedMembers,
  paginatedAircraft,
  paginatedReminders,
];

/** The schema component each assertion above names, in the same order. */
const MAPPED_COMPONENTS: readonly (keyof Schemas)[] = [
  'RolesEnum',
  'MembershipStatusStatusEnum',
  'AdminMembershipStatusEnum',
  'SourceEnum',
  'PilotCertificateTypeEnum',
  'IfrRatedEnum',
  'RatingsEnum',
  'MedicalTypeEnum',
  'OwnerTypeEnum',
  'ProviderEnum',
  'WalletEnum',
  'PaymentStatusEnum',
  'KindEnum',
  'MembershipStatus',
  'Dart',
  'Plan',
  'Profile',
  'PatchedProfileRequest',
  'AdminProfile',
  'PatchedAdminProfileRequest',
  'PatchedAdminUserRequest',
  'MemberList',
  'MemberDetail',
  'AdminMembership',
  'MemberCreateRequest',
  'PatchedMemberUpdateRequest',
  'PatchedAdminMembershipRequest',
  'AircraftSummary',
  'Aircraft',
  'PatchedAircraftRequest',
  'AdminUser',
  'Payment',
  'AdminPayment',
  'PaymentResult',
  'ReminderLog',
  'PaginatedPaymentList',
  'PaginatedAdminUserList',
  'PaginatedMemberListList',
  'PaginatedAircraftList',
  'PaginatedReminderLogList',
];

/** Vitest runs with `frontend/` as its root, so the repository root is one level up. */
const SCHEMA_PATH = resolve(process.cwd(), '../backend/openapi.json');

interface OpenApiDocument {
  components: { schemas: Record<string, unknown> };
}

function generatedComponentNames(): string[] {
  const document = JSON.parse(readFileSync(SCHEMA_PATH, 'utf8')) as OpenApiDocument;
  return Object.keys(document.components.schemas);
}

describe('api/types.ts against the generated OpenAPI schema', () => {
  it('names one schema component per type assertion', () => {
    expect(MAPPED_COMPONENTS).toHaveLength(assertions.length);
  });

  it('maps only components the backend actually generates', () => {
    const generated = new Set(generatedComponentNames());
    const missing = MAPPED_COMPONENTS.filter((name) => !generated.has(name));
    expect(missing).toEqual([]);
  });
});
