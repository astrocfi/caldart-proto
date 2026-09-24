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

import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import type { components } from './schema';
import type {
  AdminProfile,
  AdminProfilePayload,
  AdminUserPatch,
  Aircraft,
  AircraftDetail,
  AircraftPatch,
  AircraftPilot,
  AircraftSummary,
  AttachedAircraft,
  Backup,
  CheckoutRequest,
  CheckoutResponse,
  ContributionRow,
  ContributionTier,
  Dart,
  FinancePaymentTerm,
  GrantTermPayload,
  Health,
  IfrRated,
  LeaderSearchResult,
  LeaderStatus,
  LedgerMember,
  LedgerTotals,
  LoginPayload,
  MandateProvider,
  MandateStatus,
  ManualMethod,
  ManualPaymentPayload,
  MedicalType,
  MemberCreatePayload,
  MemberDetail,
  MemberLedger,
  MemberPayment,
  MemberRow,
  MemberTerm,
  MemberUpdatePayload,
  MembersPage,
  MembershipDetail,
  MembershipSource,
  MembershipState,
  MembershipStatus,
  MembershipTerm,
  MembershipTermStatus,
  NavEntry,
  NavKind,
  OwnerType,
  Paginated,
  PasswordChangePayload,
  PasswordResetConfirmPayload,
  PasswordResetRequestPayload,
  Payment,
  PaymentDetail,
  PaymentKind,
  PaymentPatch,
  PaymentPeriodSummary,
  PaymentProvider,
  PaymentRenewalAttempt,
  PaymentResult,
  PaymentState,
  PaymentSummary,
  PaymentTerm,
  PaymentWallet,
  PaymentsConfig,
  RenewalAttempt,
  RenewalConfirmRequest,
  RenewalEnvelope,
  RenewalMandate,
  RenewalOutcome,
  RenewalRunResult,
  RenewalSetupRequest,
  RenewalSetupResponse,
  PilotCertificateType,
  Plan,
  Profile,
  ProfilePatch,
  Rating,
  ReceiptSend,
  ReconciliationRow,
  Refund,
  RefundIssued,
  RefundReason,
  RefundRequest,
  RefundState,
  RefundedPayment,
  RegisterPayload,
  ReminderKind,
  ReminderLogEntry,
  ReminderRunResult,
  RenewalOutcome,
  ReportColumn,
  Role,
  RoleSlug,
  SendPasswordResetResult,
  SiteConfig,
  StatementYears,
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
const membershipState: Matches<MembershipState, Schemas['MembershipStateEnum']> = true;
const termStatus: Matches<MembershipTermStatus, Schemas['MembershipTermStatusEnum']> = true;
const membershipSource: Matches<MembershipSource, Schemas['SourceEnum']> = true;
const certificateType: Matches<PilotCertificateType, Schemas['PilotCertificateTypeEnum']> = true;
const ifrRated: Matches<IfrRated, Schemas['IfrRatedEnum']> = true;
const rating: Matches<Rating, Schemas['RatingsEnum']> = true;
const medicalType: Matches<MedicalType, Schemas['MedicalTypeEnum']> = true;
const ownerType: Matches<OwnerType, Schemas['OwnerTypeEnum']> = true;
const paymentProvider: Matches<PaymentProvider, Schemas['PaymentProviderEnum']> = true;
const paymentWallet: Matches<PaymentWallet, Schemas['WalletEnum']> = true;
const paymentState: Matches<PaymentState, Schemas['PaymentStatusEnum']> = true;
const reminderKind: Matches<ReminderKind, Schemas['ReminderKindEnum']> = true;
const navKind: Matches<NavKind, Schemas['NavKindEnum']> = true;
const paymentKind: Matches<PaymentKind, Schemas['PaymentKindEnum']> = true;
const mandateProvider: Matches<MandateProvider, Schemas['MandateProviderEnum']> = true;
const mandateStatus: Matches<MandateStatus, Schemas['MandateStatusEnum']> = true;
const renewalOutcome: Matches<RenewalOutcome, Schemas['RenewalOutcomeEnum']> = true;
const manualMethod: Matches<ManualMethod, Schemas['ManualMethodEnum']> = true;

/* ------------------------------------------------------------------- auth */
const user: Matches<User, Schemas['User']> = true;
const role: Matches<Role, Schemas['Role']> = true;
const loginPayload: Matches<LoginPayload, Schemas['LoginRequest']> = true;
const registerPayload: Matches<RegisterPayload, Schemas['RegisterRequest']> = true;
const passwordChange: Matches<PasswordChangePayload, Schemas['PasswordChangeRequest']> = true;
const passwordReset: Matches<PasswordResetRequestPayload, Schemas['PasswordResetRequest']> = true;
const passwordResetConfirm: Matches<
  PasswordResetConfirmPayload,
  Schemas['PasswordResetConfirmRequest']
> = true;
const adminUserPatch: Matches<AdminUserPatch, Schemas['PatchedAdminUserRequest']> = true;
const sendPasswordReset: Matches<SendPasswordResetResult, Schemas['SendPasswordResetResult']> =
  true;

/* ------------------------------------------------------------- membership */
const membershipStatus: Matches<MembershipStatus, Schemas['MembershipStatus']> = true;
const membershipTerm: Matches<MembershipTerm, Schemas['MembershipTerm']> = true;
const membershipDetail: Matches<MembershipDetail, Schemas['MembershipDetail']> = true;
const dart: Matches<Dart, Schemas['Dart']> = true;
const plan: Matches<Plan, Schemas['Plan']> = true;

/* ---------------------------------------------------------------- profile */
const profile: Matches<Profile, Schemas['Profile']> = true;
const profilePatch: Matches<ProfilePatch, Schemas['PatchedProfileRequest']> = true;
const adminProfile: Matches<AdminProfile, Schemas['AdminProfile']> = true;
const adminProfilePayload: Matches<AdminProfilePayload, Schemas['PatchedAdminProfileRequest']> =
  true;
const attachedAircraft: Matches<AttachedAircraft, Schemas['AttachedAircraft']> = true;

/* -------------------------------------------------- member administration */
const memberRow: Matches<MemberRow, Schemas['MemberList']> = true;
const memberDetail: Matches<MemberDetail, Schemas['MemberDetail']> = true;
const memberTerm: Matches<MemberTerm, Schemas['AdminMembership']> = true;
const memberCreate: Matches<MemberCreatePayload, Schemas['MemberCreateRequest']> = true;
const memberUpdate: Matches<MemberUpdatePayload, Schemas['PatchedMemberUpdateRequest']> = true;
const grantTerm: Matches<GrantTermPayload, Schemas['MembershipGrantRequest']> = true;
const termUpdate: Matches<TermUpdatePayload, Schemas['PatchedAdminMembershipRequest']> = true;

/* --------------------------------------------------------------- aircraft */
const aircraftSummary: Matches<AircraftSummary, Schemas['AircraftSummary']> = true;
const aircraft: Matches<Aircraft, Schemas['Aircraft']> = true;
const aircraftPatch: Matches<AircraftPatch, Schemas['PatchedAircraftRequest']> = true;
const aircraftPilot: Matches<AircraftPilot, Schemas['AircraftPilot']> = true;
const aircraftDetail: Matches<AircraftDetail, Schemas['AircraftDetail']> = true;

/* --------------------------------------------------------------- payments */
const payment: Matches<Payment, Schemas['FinancePayment']> = true;
const paymentDetail: Matches<PaymentDetail, Schemas['FinancePaymentDetail']> = true;
const financePaymentTerm: Matches<FinancePaymentTerm, Schemas['FinancePaymentTerm']> = true;
const paymentAttempt: Matches<PaymentRenewalAttempt, Schemas['PaymentRenewalAttempt']> = true;
const memberPayment: Matches<MemberPayment, Schemas['AdminPayment']> = true;
const paymentSummary: Matches<PaymentSummary, Schemas['PaymentSummary']> = true;
const paymentTerm: Matches<PaymentTerm, Schemas['PaymentTerm']> = true;
const receiptSend: Matches<ReceiptSend, Schemas['ReceiptSend']> = true;
const statementYears: Matches<StatementYears, Schemas['StatementYears']> = true;
const refundReason: Matches<RefundReason, Schemas['ReasonEnum']> = true;
const refundState: Matches<RefundState, Schemas['RefundStatusEnum']> = true;
const refund: Matches<Refund, Schemas['Refund']> = true;
const refundRequest: Matches<RefundRequest, Schemas['RefundCreateRequest']> = true;
const refundedPayment: Matches<RefundedPayment, Schemas['RefundedPayment']> = true;
const refundIssued: Matches<RefundIssued, Schemas['RefundIssued']> = true;
const paymentResult: Matches<PaymentResult, Schemas['PaymentResult']> = true;
const contributionTier: Matches<ContributionTier, Schemas['ContributionTier']> = true;
const paymentsConfig: Matches<PaymentsConfig, Schemas['PaymentsConfig']> = true;
const checkoutRequest: Matches<CheckoutRequest, Schemas['CheckoutRequest']> = true;
const checkoutResponse: Matches<CheckoutResponse, Schemas['CheckoutResponse']> = true;
const periodSummary: Matches<PaymentPeriodSummary, Schemas['PaymentPeriodSummary']> = true;
const reportColumn: Matches<ReportColumn, Schemas['ReportColumn']> = true;
const reconciliationRow: Matches<ReconciliationRow, Schemas['ReconciliationRow']> = true;
const contributionRow: Matches<ContributionRow, Schemas['ContributionRow']> = true;
const ledgerMember: Matches<LedgerMember, Schemas['LedgerMember']> = true;
const ledgerTotals: Matches<LedgerTotals, Schemas['LedgerTotals']> = true;
const memberLedger: Matches<MemberLedger, Schemas['MemberLedger']> = true;
const paymentPatch: Matches<PaymentPatch, Schemas['PatchedPaymentPatchRequest']> = true;
const manualPayment: Matches<ManualPaymentPayload, Schemas['ManualPaymentRequest']> = true;

/* ----------------------------------------------------- automatic renewal */
const mandateProvider: Matches<MandateProvider, Schemas['Provider7c9Enum']> = true;
const mandateStatus: Matches<MandateStatus, Schemas['RenewalMandateStatusEnum']> = true;
const renewalOutcome: Matches<RenewalOutcome, Schemas['RenewalAttemptOutcomeEnum']> = true;
const renewalMandate: Matches<RenewalMandate, Schemas['RenewalMandate']> = true;
const renewalEnvelope: Matches<RenewalEnvelope, Schemas['RenewalEnvelope']> = true;
const renewalAttempt: Matches<RenewalAttempt, Schemas['RenewalAttempt']> = true;
const renewalSetupRequest: Matches<RenewalSetupRequest, Schemas['RenewalSetupRequest']> = true;
const renewalSetupResponse: Matches<RenewalSetupResponse, Schemas['RenewalSetupResponse']> = true;
const renewalConfirm: Matches<RenewalConfirmRequest, Schemas['RenewalConfirmRequest']> = true;
const renewalRun: Matches<RenewalRunResult, Schemas['RenewalRunResult']> = true;

/* ----------------------------------------------------------------- leader */
const leaderSearch: Matches<LeaderSearchResult, Schemas['LeaderSearchResult']> = true;
const leaderStatus: Matches<LeaderStatus, Schemas['LeaderStatus']> = true;

/* -------------------------------------------------- reminders and system */
const reminderLog: Matches<ReminderLogEntry, Schemas['ReminderLog']> = true;
const reminderRun: Matches<ReminderRunResult, Schemas['ReminderRunResult']> = true;
const health: Matches<Health, Schemas['Health']> = true;
const backup: Matches<Backup, Schemas['Backup']> = true;

/* ------------------------------------------------------------------- site */
const navEntry: Matches<NavEntry, Schemas['NavEntry']> = true;
const membersPage: Matches<MembersPage, Schemas['MembersPage']> = true;
const siteConfig: Matches<SiteConfig, Schemas['SiteConfig']> = true;

/* ------------------------------------------------------------- pagination */
const paginatedPayments: Matches<Paginated<Payment>, Schemas['PaginatedFinancePaymentList']> = true;
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
  paymentKind,
  mandateProvider,
  mandateStatus,
  renewalOutcome,
  manualMethod,
  paymentWallet,
  paymentState,
  reminderKind,
  navKind,
  user,
  role,
  loginPayload,
  registerPayload,
  passwordChange,
  passwordReset,
  passwordResetConfirm,
  adminUserPatch,
  sendPasswordReset,
  membershipStatus,
  membershipTerm,
  membershipDetail,
  dart,
  plan,
  profile,
  profilePatch,
  adminProfile,
  adminProfilePayload,
  attachedAircraft,
  memberRow,
  memberDetail,
  memberTerm,
  memberCreate,
  memberUpdate,
  grantTerm,
  termUpdate,
  aircraftSummary,
  aircraft,
  aircraftPatch,
  aircraftPilot,
  aircraftDetail,
  payment,
  paymentDetail,
  financePaymentTerm,
  paymentAttempt,
  memberPayment,
  paymentSummary,
  paymentTerm,
  receiptSend,
  statementYears,
  refundReason,
  refundState,
  refund,
  refundRequest,
  refundedPayment,
  refundIssued,
  paymentResult,
  contributionTier,
  paymentsConfig,
  checkoutRequest,
  checkoutResponse,
  periodSummary,
  reportColumn,
  reconciliationRow,
  contributionRow,
  ledgerMember,
  ledgerTotals,
  memberLedger,
  paymentPatch,
  manualPayment,
  mandateProvider,
  mandateStatus,
  renewalOutcome,
  renewalMandate,
  renewalEnvelope,
  renewalAttempt,
  renewalSetupRequest,
  renewalSetupResponse,
  renewalConfirm,
  renewalRun,
  leaderSearch,
  leaderStatus,
  reminderLog,
  reminderRun,
  health,
  backup,
  navEntry,
  membersPage,
  siteConfig,
  paginatedPayments,
  paginatedUsers,
  paginatedMembers,
  paginatedAircraft,
  paginatedReminders,
];

/** The schema component each assertion above names, in the same order. */
const MAPPED_COMPONENTS: readonly (keyof Schemas)[] = [
  'RolesEnum',
  'MembershipStateEnum',
  'MembershipTermStatusEnum',
  'SourceEnum',
  'PilotCertificateTypeEnum',
  'IfrRatedEnum',
  'RatingsEnum',
  'MedicalTypeEnum',
  'OwnerTypeEnum',
  'PaymentProviderEnum',
  'WalletEnum',
  'PaymentStatusEnum',
  'ReminderKindEnum',
  'NavKindEnum',
  'PaymentKindEnum',
  'MandateProviderEnum',
  'MandateStatusEnum',
  'RenewalOutcomeEnum',
  'ManualMethodEnum',
  'User',
  'Role',
  'LoginRequest',
  'RegisterRequest',
  'PasswordChangeRequest',
  'PasswordResetRequest',
  'PasswordResetConfirmRequest',
  'PatchedAdminUserRequest',
  'SendPasswordResetResult',
  'MembershipStatus',
  'MembershipTerm',
  'MembershipDetail',
  'Dart',
  'Plan',
  'Profile',
  'PatchedProfileRequest',
  'AdminProfile',
  'PatchedAdminProfileRequest',
  'AttachedAircraft',
  'MemberList',
  'MemberDetail',
  'AdminMembership',
  'MemberCreateRequest',
  'PatchedMemberUpdateRequest',
  'MembershipGrantRequest',
  'PatchedAdminMembershipRequest',
  'AircraftSummary',
  'Aircraft',
  'PatchedAircraftRequest',
  'AircraftPilot',
  'AircraftDetail',
  'FinancePayment',
  'FinancePaymentDetail',
  'FinancePaymentTerm',
  'PaymentRenewalAttempt',
  'AdminPayment',
  'PaymentSummary',
  'PaymentTerm',
  'ReceiptSend',
  'StatementYears',
  'ReasonEnum',
  'RefundStatusEnum',
  'Refund',
  'RefundCreateRequest',
  'RefundedPayment',
  'RefundIssued',
  'PaymentResult',
  'ContributionTier',
  'PaymentsConfig',
  'CheckoutRequest',
  'CheckoutResponse',
  'PaymentPeriodSummary',
  'ReportColumn',
  'ReconciliationRow',
  'ContributionRow',
  'LedgerMember',
  'LedgerTotals',
  'MemberLedger',
  'PatchedPaymentPatchRequest',
  'ManualPaymentRequest',
  'Provider7c9Enum',
  'RenewalMandateStatusEnum',
  'RenewalAttemptOutcomeEnum',
  'RenewalMandate',
  'RenewalEnvelope',
  'RenewalAttempt',
  'RenewalSetupRequest',
  'RenewalSetupResponse',
  'RenewalConfirmRequest',
  'RenewalRunResult',
  'LeaderSearchResult',
  'LeaderStatus',
  'ReminderLog',
  'ReminderRunResult',
  'Health',
  'Backup',
  'NavEntry',
  'MembersPage',
  'SiteConfig',
  'PaginatedFinancePaymentList',
  'PaginatedAdminUserList',
  'PaginatedMemberListList',
  'PaginatedAircraftList',
  'PaginatedReminderLogList',
];

/** Vitest runs with `frontend/` as its root, so the repository root is one level up. */
const SCHEMA_PATH = resolve(process.cwd(), '../backend/openapi.json');

/** What to run when the generated description is not on disk. */
const REGENERATE_COMMAND = 'npm run schema';

interface OpenApiDocument {
  components: { schemas: Record<string, unknown> };
}

function generatedComponentNames(): string[] {
  if (!existsSync(SCHEMA_PATH)) {
    throw new Error(
      `The OpenAPI description is missing at ${SCHEMA_PATH}. ` +
        `It is build output, not a source file: run \`${REGENERATE_COMMAND}\` in frontend/ ` +
        `(or \`make check-backend\`) to write it, then run the tests again.`,
    );
  }
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
