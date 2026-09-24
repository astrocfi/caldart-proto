/** Test data for the member payments, renewal, and checkout suites.  Not shipped. */
import type { PaymentSummary, PaymentsConfig, Plan, RenewalMandate } from '@/portal/api/types';

export const ANNUAL_PLAN: Plan = {
  slug: 'annual',
  name: 'Annual',
  price_cents: 4500,
  duration_days: 365,
  description: 'One year of CalDART membership.',
};

export const LIFE_PLAN: Plan = {
  slug: 'life',
  name: 'Life',
  price_cents: 90000,
  duration_days: null,
  description: 'Membership for life.',
};

/** A payments config offering both plans and every provider a browser can use. */
export function makePaymentsConfig(overrides: Partial<PaymentsConfig> = {}): PaymentsConfig {
  return {
    providers: ['stripe', 'paypal', 'mock'],
    stripe_publishable_key: 'pk_test_fixture',
    paypal_client_id: 'paypal-client-fixture',
    plans: [ANNUAL_PLAN, LIFE_PLAN],
    contribution_tiers: [
      { label: 'No thank you', cents: 0 },
      { label: 'Supporter', cents: 2500 },
    ],
    max_contribution_cents: 9_999_900,
    ...overrides,
  };
}

/** One row of `GET /me/payments`, with `overrides` merged over a settled card payment. */
export function makePaymentSummary(overrides: Partial<PaymentSummary> = {}): PaymentSummary {
  return {
    id: 414,
    plan: 'Annual',
    kind: 'membership',
    amount_cents: 4500,
    plan_amount_cents: 4500,
    contribution_cents: 0,
    refunded_cents: 0,
    provider: 'stripe',
    wallet: 'card',
    status: 'succeeded',
    paid_on: '2026-03-14',
    completed_at: '2026-03-14T18:02:11Z',
    receipt_sent_at: '2026-03-14T18:02:13Z',
    membership: { id: 87, starts_on: '2026-03-14', ends_on: '2027-03-13' },
    ...overrides,
  };
}

/** A mandate as `GET /me/renewal` carries it, active on a saved Visa by default. */
export function makeMandate(overrides: Partial<RenewalMandate> = {}): RenewalMandate {
  return {
    id: 12,
    user_id: 1,
    user_name: 'Marta Reyes',
    user_email: 'member@example.org',
    plan: 'annual',
    plan_name: 'Annual',
    kind: 'both',
    contribution_cents: 2500,
    amount_cents: 7000,
    provider: 'stripe',
    method_label: 'Visa ending 4242, expires 03/2028',
    method_brand: 'visa',
    method_last4: '4242',
    method_exp_month: 3,
    method_exp_year: 2028,
    status: 'active',
    failure_count: 0,
    next_charge_on: '2027-03-12',
    last_error: '',
    last_charged_at: '2026-03-14T18:22:05Z',
    canceled_at: null,
    created_at: '2025-03-14T18:21:58Z',
    ...overrides,
  };
}
