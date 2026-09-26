/** Test data for the finance screens.  Not shipped. */
import type {
  FinanceMember,
  MemberLedger,
  Payment,
  PaymentDetail,
  PaymentPeriodSummary,
  Refund,
  RenewalMandate,
  ReportColumn,
} from '@/portal/api/types';

/** The column registry, cut to the columns the finance tests read. */
export const TEST_COLUMNS: ReportColumn[] = [
  { key: 'paid_on', label: 'Date', default: true },
  { key: 'receipt_number', label: 'Receipt', default: false },
  { key: 'name', label: 'Name', default: true },
  { key: 'total', label: 'Total', default: true },
  { key: 'fee', label: 'Fee', default: true },
  { key: 'net', label: 'Net', default: true },
  { key: 'refunded', label: 'Refunded', default: true },
  { key: 'status', label: 'Status', default: true },
];

/** One period of the summary, with `overrides` replacing any default field. */
export function makePeriod(overrides: Partial<PaymentPeriodSummary> = {}): PaymentPeriodSummary {
  return {
    period: '2026-01',
    count: 2,
    total_cents: 21_000,
    plan_cents: 9_000,
    contribution_cents: 12_000,
    fee_cents: 639,
    net_cents: 20_361,
    refunded_cents: 2_500,
    by_provider: { stripe: 14_500, paypal: 6_500 },
    ...overrides,
  };
}

/** One finance list row, with `overrides` replacing any default field. */
export function makePayment(overrides: Partial<Payment> = {}): Payment {
  return {
    id: 412,
    user_id: 37,
    user_name: 'Marta Reyes',
    user_email: 'marta@example.org',
    plan: 'Annual',
    kind: 'both',
    amount_cents: 14_500,
    plan_amount_cents: 4_500,
    contribution_cents: 10_000,
    fee_cents: 450,
    net_cents: 14_050,
    refunded_cents: 0,
    currency: 'usd',
    provider: 'stripe',
    wallet: 'apple_pay',
    provider_ref: 'pi_123',
    status: 'succeeded',
    receipt_number: 'CALDART-000412',
    receipt_sent_at: '2026-01-08T20:00:10Z',
    paid_on: '2026-01-08',
    received_on: null,
    reconciled_on: null,
    reconciled_by: null,
    recorded_by: null,
    note: '',
    membership: { id: 88, starts_on: '2026-01-09', ends_on: '2027-01-08', status: 'active' },
    renewal_attempt: null,
    created_at: '2026-01-08T20:00:00Z',
    completed_at: '2026-01-08T20:00:05Z',
    ...overrides,
  };
}

/** One refund against a payment, with `overrides` replacing any default field. */
export function makeRefund(overrides: Partial<Refund> = {}): Refund {
  return {
    id: 9,
    payment_id: 412,
    amount_cents: 2_500,
    reason: 'requested_by_member',
    note: '',
    status: 'succeeded',
    provider_ref: 're_123',
    requested_by_id: 7,
    refunded_at: '2026-02-14T11:02:00Z',
    created_at: '2026-02-14T11:01:58Z',
    ...overrides,
  };
}

/** One payment with its refunds, as the detail screen reads it. */
export function makeDetail(overrides: Partial<PaymentDetail> = {}): PaymentDetail {
  return { ...makePayment(), refunds: [], ...overrides };
}

/** A member's standing renewal authority, with `overrides` merged over it. */
export function makeMandate(overrides: Partial<RenewalMandate> = {}): RenewalMandate {
  return {
    id: 4,
    user_id: 37,
    user_name: 'Marta Reyes',
    user_email: 'marta@example.org',
    plan: 'annual',
    plan_name: 'Annual',
    kind: 'both',
    cadence: 'yearly',
    contribution_cents: 2_000,
    amount_cents: 6_500,
    provider: 'stripe',
    method_label: 'Visa ending 4242, expires 03/2028',
    method_brand: 'visa',
    method_last4: '4242',
    method_exp_month: 3,
    method_exp_year: 2028,
    status: 'active',
    failure_count: 0,
    next_charge_on: '2027-01-07',
    last_error: '',
    last_charged_at: '2026-01-05T06:30:12Z',
    canceled_at: null,
    created_at: '2025-01-05T06:30:12Z',
    ...overrides,
  };
}

/**
 * A life member's standing authority, which charges a contribution alone and
 * renews no plan, with `overrides` merged over it.
 */
export function makeContributionMandate(overrides: Partial<RenewalMandate> = {}): RenewalMandate {
  return makeMandate({
    plan: null,
    plan_name: null,
    kind: 'contribution',
    contribution_cents: 5_000,
    amount_cents: 5_000,
    ...overrides,
  });
}

/** One member's whole money history, with `overrides` merged over it. */
export function makeLedger(overrides: Partial<MemberLedger> = {}): MemberLedger {
  return {
    user: {
      id: 37,
      name: 'Marta Reyes',
      email: 'marta@example.org',
      membership: {
        status: 'current',
        expires_on: '2027-01-08',
        plan: 'Annual',
        is_lifetime: false,
      },
    },
    totals: {
      paid_cents: 43_500,
      contribution_cents: 11_000,
      fee_cents: 1_380,
      refunded_cents: 2_500,
    },
    payments: [makeDetail()],
    mandate: null,
    statement_years: [2026],
    ...overrides,
  };
}

/** One row of the finance area's member search. */
export function makeFinanceMember(overrides: Partial<FinanceMember> = {}): FinanceMember {
  return {
    user_id: 37,
    name: 'Marta Reyes',
    email: 'marta@example.org',
    membership: {
      status: 'current',
      expires_on: '2027-01-08',
      plan: 'Annual',
      is_lifetime: false,
    },
    ...overrides,
  };
}
