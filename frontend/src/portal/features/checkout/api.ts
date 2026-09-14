/**
 * Everything the checkout says to `/api/v1/payments/...`.
 *
 * Amounts are never sent: the server recomputes the total from the plan and
 * the contribution, so a request only names what the member chose.
 */
import { useQuery } from '@tanstack/react-query';

import { api } from '../../api/client';
import type {
  CheckoutRequest,
  CheckoutResponse,
  PaymentProvider,
  PaymentResult,
  PaymentsConfig,
} from '../../api/types';

export const PAYMENTS_CONFIG_KEY = ['payments', 'config'] as const;

/**
 * True when a rejection is `fetch` refusing to run because its `AbortSignal` fired.
 *
 * An aborted request carries no news about the payment, so a caller that asked for the
 * abort has nothing to report to the member.
 */
export function isAbortError(caught: unknown): boolean {
  return caught instanceof DOMException && caught.name === 'AbortError';
}

export function fetchPaymentsConfig(): Promise<PaymentsConfig> {
  return api.get<PaymentsConfig>('/payments/config');
}

/** Plans, contribution tiers and the providers this deployment can offer. */
export function usePaymentsConfig() {
  return useQuery({
    queryKey: PAYMENTS_CONFIG_KEY,
    queryFn: fetchPaymentsConfig,
    staleTime: 5 * 60_000,
  });
}

/**
 * Start a payment, and with it the provider-side session the panel renders.
 *
 * Pass `signal` to abandon the attempt: an aborted request never reaches the server, so
 * a panel that aborts in its effect cleanup leaves no orphaned PaymentIntent behind.
 */
export function createCheckout(
  request: CheckoutRequest,
  signal?: AbortSignal,
): Promise<CheckoutResponse> {
  return api.post<CheckoutResponse>('/payments/checkout', request, { signal });
}

/**
 * Tell the server that Stripe has finished with a PaymentIntent.
 *
 * The call is idempotent, and `signal` abandons it without changing what the server
 * has already recorded.
 */
export function confirmStripePayment(
  paymentId: number,
  paymentIntentId: string,
  signal?: AbortSignal,
): Promise<PaymentResult> {
  return api.post<PaymentResult>(
    '/payments/stripe/confirm',
    {
      payment_id: paymentId,
      payment_intent_id: paymentIntentId,
    },
    { signal },
  );
}

export function capturePayPalOrder(paymentId: number, orderId: string): Promise<PaymentResult> {
  return api.post<PaymentResult>('/payments/paypal/capture', {
    payment_id: paymentId,
    order_id: orderId,
  });
}

export function completeMockPayment(
  paymentId: number,
  outcome: 'succeed' | 'fail',
): Promise<PaymentResult> {
  return api.post<PaymentResult>('/payments/mock/complete', {
    payment_id: paymentId,
    outcome,
  });
}

/** Read a payment's current status; `signal` abandons a poll that is no longer wanted. */
export function fetchPayment(paymentId: number, signal?: AbortSignal): Promise<PaymentResult> {
  return api.get<PaymentResult>(`/payments/${paymentId}`, { signal });
}

/** Human label for each provider tab. */
export const PROVIDER_LABELS: Record<PaymentProvider, string> = {
  stripe: 'Card · Apple Pay · Google Pay',
  paypal: 'PayPal',
  mock: 'Test payment',
};

/** Tab order, so the list does not jump about with the server's ordering. */
export const PROVIDER_ORDER: PaymentProvider[] = ['stripe', 'paypal', 'mock'];
