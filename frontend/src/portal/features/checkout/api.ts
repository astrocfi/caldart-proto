/**
 * Everything the checkout says to `/api/v1/payments/...`.
 *
 * Amounts are never sent: the server recomputes the total from the plan and
 * the contribution, so a request only names what the member chose.
 */
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';

import { ApiError, api } from '@/portal/api/client';
import type {
  CheckoutRequest,
  CheckoutResponse,
  PaymentProvider,
  PaymentResult,
  PaymentsConfig,
} from '@/portal/api/types';
import type { ProviderPanelProps } from './types';

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

/** The `code` a donation is refused with while the member's renewal takes a contribution. */
const RENEWAL_CONTRIBUTION_CODE = 'renewal_contribution';

/** Whether `caught` is the server refusing a donation while the renewal takes a contribution. */
function isRenewalContribution(caught: ApiError): boolean {
  const { body } = caught;
  return (
    caught.status === 400 &&
    typeof body === 'object' &&
    body !== null &&
    (body as Record<string, unknown>).code === RENEWAL_CONTRIBUTION_CODE
  );
}

/**
 * What a payment panel shows for a request that failed, or null for nothing.
 *
 * The server's refusal of a donation because the member's renewal already takes a
 * contribution is a question, not an error: its sentence goes to
 * `onRenewalContribution`, for the checkout to ask whether to move the contribution,
 * and the panel shows nothing.  Any other `ApiError` shows the server's message, and
 * anything else `fallback`.
 *
 * @param caught - What the request rejected with.
 * @param fallback - The panel's own wording for a failure that carries none.
 * @param onRenewalContribution - Handed the server's sentence for that one refusal.
 * @returns The message to show, or null.
 */
export function panelErrorMessage(
  caught: unknown,
  fallback: string,
  onRenewalContribution?: (detail: string) => void,
): string | null {
  if (!(caught instanceof ApiError)) return fallback;
  if (onRenewalContribution !== undefined && isRenewalContribution(caught)) {
    onRenewalContribution(caught.message);
    return null;
  }
  return caught.message;
}

/** What a checkout request is built from: the panel's choices, less the display total. */
export type CheckoutFields = Pick<
  ProviderPanelProps,
  'plan' | 'contributionCents' | 'autoRenew' | 'cadence' | 'removeRenewalContribution'
>;

/**
 * The `POST /payments/checkout` body for `fields`, paid with `provider`.
 *
 * `cadence` travels only with a standing authority, and
 * `remove_renewal_contribution` only when the member agreed to it: the server's
 * defaults are a yearly authority and no move.
 */
export function checkoutRequest(
  {
    plan,
    contributionCents,
    autoRenew,
    cadence,
    removeRenewalContribution = false,
  }: CheckoutFields,
  provider: PaymentProvider,
): CheckoutRequest {
  const request: CheckoutRequest = {
    plan,
    contribution_cents: contributionCents,
    provider,
    auto_renew: autoRenew,
  };
  if (autoRenew && cadence !== undefined) request.cadence = cadence;
  if (autoRenew && removeRenewalContribution) request.remove_renewal_contribution = true;
  return request;
}

/** Fetch the plans, contribution tiers and providers this deployment can offer. */
export function fetchPaymentsConfig(): Promise<PaymentsConfig> {
  return api.get<PaymentsConfig>('/payments/config');
}

/** Plans, contribution tiers and the providers this deployment can offer. */
export function usePaymentsConfig(): UseQueryResult<PaymentsConfig> {
  return useQuery({
    queryKey: PAYMENTS_CONFIG_KEY,
    queryFn: fetchPaymentsConfig,
    staleTime: 5 * 60_000,
  });
}

/**
 * Start a payment, and with it the provider-side session the panel renders.
 *
 * Pass `signal` to abandon the attempt. What the abort buys depends on when it lands: one
 * that fires before `fetch` dispatches, as an effect cleanup run straight after setup
 * does, stops the request outright and no PaymentIntent is created; one that fires
 * mid-flight only discards the answer, and the intent the server made stays unconfirmed.
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

/** Capture a PayPal order the member approved, activating the membership on success. */
export function capturePayPalOrder(paymentId: number, orderId: string): Promise<PaymentResult> {
  return api.post<PaymentResult>('/payments/paypal/capture', {
    payment_id: paymentId,
    order_id: orderId,
  });
}

/** Resolve a mock-provider payment as succeeded or failed. */
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
  manual: 'Recorded by hand',
};

/** Tab order, so the list does not jump about with the server's ordering. */
export const PROVIDER_ORDER: PaymentProvider[] = ['stripe', 'paypal', 'mock'];
