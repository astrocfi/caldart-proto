import { describe, expect, it } from 'vitest';

import { declineReason, methodLabel } from './labels';

describe('declineReason', () => {
  it.each([
    ['Your card was declined', 'Card declined'],
    ['Your card was declined.', 'Card declined'],
    ['Your card has expired.', 'Card declined (member was told: “Your card has expired”)'],
    ['PayPal refused the saved payment method.', 'PayPal refused the saved payment method'],
    [
      'PayPal captured $40.00, not $45.00.',
      'Payment could not be verified (“PayPal captured $40.00, not $45.00”)',
    ],
    [
      'PaymentIntent amount does not match this payment.',
      'Payment could not be verified (“PaymentIntent amount does not match this payment”)',
    ],
    [
      'PayPal rejected the request: INSTRUMENT_DECLINED',
      'Charge refused (“PayPal rejected the request: INSTRUMENT_DECLINED”)',
    ],
    ['', ''],
  ])('reads %j as %j', (recorded, expected) => {
    expect(declineReason(recorded)).toBe(expected);
  });
});

describe('methodLabel', () => {
  it('names the method once when the provider and the way of paying share a name', () => {
    expect(methodLabel('paypal', 'paypal')).toBe('PayPal');
  });

  it('names both when they differ', () => {
    expect(methodLabel('stripe', 'apple_pay')).toBe('Stripe · Apple Pay');
  });
});
