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

export function createCheckout(request: CheckoutRequest): Promise<CheckoutResponse> {
  return api.post<CheckoutResponse>('/payments/checkout', request);
}

export function confirmStripePayment(
  paymentId: number,
  paymentIntentId: string,
): Promise<PaymentResult> {
  return api.post<PaymentResult>('/payments/stripe/confirm', {
    payment_id: paymentId,
    payment_intent_id: paymentIntentId,
  });
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

export function fetchPayment(paymentId: number): Promise<PaymentResult> {
  return api.get<PaymentResult>(`/payments/${paymentId}`);
}

/** Human label for each provider tab. */
export const PROVIDER_LABELS: Record<PaymentProvider, string> = {
  stripe: 'Card · Apple Pay · Google Pay',
  paypal: 'PayPal',
  mock: 'Test payment',
};

/** Tab order, so the list does not jump about with the server's ordering. */
export const PROVIDER_ORDER: PaymentProvider[] = ['stripe', 'paypal', 'mock'];
