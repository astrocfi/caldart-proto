/**
 * The payment enums as the finance screens name them.
 *
 * The provider, status and wallet wording is the portal's shared vocabulary
 * (`@/portal/choices`), so the member's dashboard, their administrator's ledger
 * and the finance list cannot disagree about what "succeeded" is called.  The
 * rest are named here because the finance area is the only place they appear.
 */
import type {
  MandateKind,
  MandateStatus,
  ManualMethod,
  PaymentKind,
  RefundReason,
  RefundState,
} from '@/portal/api/types';

export {
  PAYMENT_PROVIDER_LABELS as PROVIDER_LABELS,
  PAYMENT_STATUS_LABELS as STATUS_LABELS,
  PAYMENT_WALLET_LABELS as WALLET_LABELS,
} from '@/portal/choices';
export { paymentStatusTone as statusTone } from '@/portal/components/StatusChip';

/** What a payment bought. */
export const KIND_LABELS: Record<PaymentKind, string> = {
  membership: 'Membership',
  contribution: 'Contribution',
  both: 'Membership and contribution',
};

/** Why a refund was issued, in the wording the refund form offers. */
export const REFUND_REASON_LABELS: Record<RefundReason, string> = {
  requested_by_member: 'The member asked for it',
  duplicate: 'Duplicate payment',
  error: 'Charged in error',
  fraudulent: 'Fraudulent',
  other: 'Something else',
};

/** How far a refund has got. */
export const REFUND_STATUS_LABELS: Record<RefundState, string> = {
  pending: 'Pending',
  succeeded: 'Succeeded',
  failed: 'Failed',
};

/** How money taken by hand was presented. */
export const MANUAL_METHOD_LABELS: Record<ManualMethod, string> = {
  check: 'Check',
  cash: 'Cash',
  bank_transfer: 'Bank transfer',
  other: 'Other',
};

/** Where a member's standing renewal authority stands. */
export const MANDATE_STATUS_LABELS: Record<MandateStatus, string> = {
  pending: 'Waiting for the first payment',
  active: 'On',
  paused: 'Paused after failed charges',
  canceled: 'Turned off',
};

/**
 * What a standing renewal authority is called on the finance screens, by what
 * it charges for.  `contribution` is a recurring donation, which names no plan.
 */
export const MANDATE_KIND_LABELS: Record<MandateKind, string> = {
  renewal: 'Automatic renewal',
  both: 'Automatic renewal and contribution',
  contribution: 'Recurring donation',
};

/**
 * The same wording, keyed by a payment's own kind, for the payment detail
 * screen's row that says whether a charge came from a standing authority.
 */
export const PAYMENT_AUTOMATIC_LABELS: Record<PaymentKind, string> = {
  membership: 'Automatic renewal',
  both: 'Automatic renewal and contribution',
  contribution: 'Recurring donation',
};
