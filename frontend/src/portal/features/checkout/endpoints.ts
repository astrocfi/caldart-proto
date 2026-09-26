/**
 * The calls a payment panel makes, gathered so another host can supply its own.
 *
 * The portal's checkout talks to `/payments/...` as the signed-in member; the public
 * donation page talks to `/donations/...` with a token instead.  Both render the same
 * Stripe, PayPal, and mock panels, which make every call through a `PaymentEndpoints`
 * and default to the portal's.
 */
import type { CheckoutRequest, CheckoutResponse, PaymentResult } from '@/portal/api/types';
import {
  capturePayPalOrder,
  completeMockPayment,
  confirmStripePayment,
  createCheckout,
  fetchPayment,
} from './api';

/** What a mock payment can be told to do. */
export type MockOutcome = 'succeed' | 'fail';

/** Every call a payment panel, or the return from a redirect, makes to the server. */
export interface PaymentEndpoints {
  /** Start a payment for `request`; `signal` abandons it. */
  createCheckout: (request: CheckoutRequest, signal?: AbortSignal) => Promise<CheckoutResponse>;
  /** Tell the server that Stripe has finished with the payment's intent. */
  confirmStripe: (
    paymentId: number,
    paymentIntentId: string,
    signal?: AbortSignal,
  ) => Promise<PaymentResult>;
  /** Capture the PayPal order the payer approved. */
  capturePayPal: (paymentId: number, orderId: string) => Promise<PaymentResult>;
  /** Succeed or fail a mock payment. */
  completeMock: (paymentId: number, outcome: MockOutcome) => Promise<PaymentResult>;
  /** Read the payment's status; `signal` abandons a poll that is no longer wanted. */
  fetchPayment: (paymentId: number, signal?: AbortSignal) => Promise<PaymentResult>;
  /** Where Stripe sends the browser back after a method that leaves the page. */
  stripeReturnUrl: (paymentId: number) => string;
}

/** The portal's own address for a redirect-based Stripe method to come back to. */
function portalReturnUrl(paymentId: number): string {
  const origin = typeof window === 'undefined' ? '' : window.location.origin;
  return `${origin}/portal/join/done?payment_id=${paymentId}`;
}

/** The signed-in member's checkout, through `/payments/...`. */
export const PORTAL_ENDPOINTS: PaymentEndpoints = {
  createCheckout,
  confirmStripe: confirmStripePayment,
  capturePayPal: capturePayPalOrder,
  completeMock: completeMockPayment,
  fetchPayment,
  stripeReturnUrl: portalReturnUrl,
};
