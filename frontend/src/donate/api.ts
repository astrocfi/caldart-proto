/**
 * Everything the public donation form says to `/api/v1/donations/...`.
 *
 * Nobody signs in to give, so the calls that finish a payment prove the caller
 * with the `token` the checkout answered.  `donationEndpoints` wraps the calls in
 * the `PaymentEndpoints` shape the portal's payment panels take, so the page renders
 * the same Stripe, PayPal, and mock panels as the portal.
 */
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type {
  DonationCheckoutRequest,
  DonationCheckoutResponse,
  DonationsConfig,
  PaymentResult,
} from '@/portal/api/types';
import type { PaymentEndpoints } from '@/portal/features/checkout/endpoints';

/** The giver's part of a checkout body: everything but the amount and the provider. */
export type DonorBody = Omit<DonationCheckoutRequest, 'contribution_cents' | 'provider'>;

/** Read what the form offers: providers, amounts, and the profile's choices. */
export function useDonationsConfig(configUrl: string): UseQueryResult<DonationsConfig> {
  return useQuery({
    queryKey: ['donations', 'config', configUrl],
    queryFn: () => api.get<DonationsConfig>(configUrl),
    staleTime: 5 * 60_000,
  });
}

/** Where a gift that left the page comes back to, with what proves it. */
export function returnAddress(returnUrl: string, paymentId: number, token: string): string {
  const origin = typeof window === 'undefined' ? '' : window.location.origin;
  const query = new URLSearchParams({ payment_id: String(paymentId), token });
  return `${origin}${returnUrl}?${query.toString()}`;
}

export interface DonationEndpointsOptions {
  /** The page to come back to after a payment method that leaves it. */
  returnUrl: string;
  /** Who is giving; null where no gift will be started, as on the return from a redirect. */
  donor: DonorBody | null;
  /** Tokens already known, by payment id: the one a redirect brought back. */
  tokens?: ReadonlyMap<number, string>;
}

/**
 * The payment panels' calls, made through `/donations/...` for `donor`.
 *
 * Starting a payment sends the giver's details with the amount and the provider,
 * and keeps the token it answers; every later call for that payment sends it back.
 *
 * @throws Error from `createCheckout` when `donor` is null.
 */
export function donationEndpoints({
  returnUrl,
  donor,
  tokens = new Map(),
}: DonationEndpointsOptions): PaymentEndpoints {
  const known = new Map(tokens);
  const tokenFor = (paymentId: number): string => known.get(paymentId) ?? '';

  return {
    createCheckout: async (request, signal) => {
      if (donor === null) throw new Error('Nobody is giving yet.');
      const body: DonationCheckoutRequest = {
        ...donor,
        contribution_cents: request.contribution_cents,
        provider: request.provider,
      };
      const started = await api.post<DonationCheckoutResponse>('/donations/checkout', body, {
        signal,
      });
      known.set(started.payment_id, started.token);
      return started;
    },
    confirmStripe: (paymentId, paymentIntentId, signal) =>
      api.post<PaymentResult>(
        '/donations/stripe/confirm',
        { payment_id: paymentId, payment_intent_id: paymentIntentId, token: tokenFor(paymentId) },
        { signal },
      ),
    capturePayPal: (paymentId, orderId) =>
      api.post<PaymentResult>('/donations/paypal/capture', {
        payment_id: paymentId,
        order_id: orderId,
        token: tokenFor(paymentId),
      }),
    completeMock: (paymentId, outcome) =>
      api.post<PaymentResult>('/donations/mock/complete', {
        payment_id: paymentId,
        outcome,
        token: tokenFor(paymentId),
      }),
    fetchPayment: (paymentId, signal) =>
      api.get<PaymentResult>(`/donations/${paymentId}`, {
        query: { token: tokenFor(paymentId) },
        signal,
      }),
    stripeReturnUrl: (paymentId) => returnAddress(returnUrl, paymentId, tokenFor(paymentId)),
  };
}
