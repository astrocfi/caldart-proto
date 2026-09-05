/** Short human names for the payment enums (PLAN §4.4). */
import type { PaymentProvider, PaymentState, PaymentWallet } from '../../api/types';

export const PROVIDER_LABELS: Record<PaymentProvider, string> = {
  stripe: 'Stripe',
  paypal: 'PayPal',
  mock: 'Test',
};

export const STATUS_LABELS: Record<PaymentState, string> = {
  pending: 'Pending',
  succeeded: 'Succeeded',
  failed: 'Failed',
  refunded: 'Refunded',
};

export const WALLET_LABELS: Record<PaymentWallet, string> = {
  card: 'Card',
  apple_pay: 'Apple Pay',
  google_pay: 'Google Pay',
  link: 'Link',
  paypal: 'PayPal',
  mock: 'Test',
  unknown: '—',
};

/** Chip tone for a payment status, reusing the shared status palette. */
export function statusTone(status: PaymentState): 'current' | 'expiring' | 'expired' | 'none' {
  if (status === 'succeeded') return 'current';
  if (status === 'pending') return 'expiring';
  if (status === 'failed') return 'expired';
  return 'none';
}
