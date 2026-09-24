/**
 * Everything the member's own Payments screen says to the API.
 *
 * The payment rows themselves come from `@/portal/features/profile/api`, which
 * already owns `GET /me/payments`; this module adds the standing authority to
 * renew, the contribution statements, and the two download addresses.
 *
 * Every mutation writes the mandate it was answered with straight into the
 * renewal query, so the card redraws from the server's own view of the
 * authority rather than from a guess made in the browser.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { API_BASE, api } from '@/portal/api/client';
import type {
  RenewalConfirmRequest,
  RenewalEnvelope,
  RenewalSetupRequest,
  RenewalSetupResponse,
  StatementYears,
} from '@/portal/api/types';

export const RENEWAL_KEY = ['me', 'renewal'] as const;
export const STATEMENT_YEARS_KEY = ['me', 'payments', 'statements'] as const;

/** The signed-in member's standing authority to renew, via `GET /me/renewal`. */
export function useRenewal(): UseQueryResult<RenewalEnvelope> {
  return useQuery({
    queryKey: RENEWAL_KEY,
    queryFn: () => api.get<RenewalEnvelope>('/me/renewal'),
  });
}

/** The calendar years the member may download a contribution statement for. */
export function useStatementYears(): UseQueryResult<StatementYears> {
  return useQuery({
    queryKey: STATEMENT_YEARS_KEY,
    queryFn: () => api.get<StatementYears>('/me/payments/statements'),
  });
}

/** Where a receipt PDF is downloaded from. */
export function receiptUrl(paymentId: number): string {
  return `${API_BASE}/me/payments/${paymentId}/receipt.pdf`;
}

/** Where a calendar year's contribution statement PDF is downloaded from. */
export function statementUrl(year: number): string {
  return `${API_BASE}/me/payments/statements/${year}.pdf`;
}

/**
 * Start saving a payment method, via `POST /me/renewal/setup`.
 *
 * The answer carries whatever the chosen provider's browser SDK needs: a Stripe
 * SetupIntent secret, a PayPal vault setup token, or nothing at all for the mock
 * provider.  Nothing is charged, and the mandate stays `pending` until it is
 * confirmed.
 */
export function useStartRenewalSetup(): UseMutationResult<
  RenewalSetupResponse,
  Error,
  RenewalSetupRequest
> {
  return useMutation({
    mutationFn: (request: RenewalSetupRequest) =>
      api.post<RenewalSetupResponse>('/me/renewal/setup', request),
  });
}

/**
 * Save the method the browser collected and make the mandate active, via
 * `POST /me/renewal/confirm`.
 *
 * Both provider references travel on every request because the body carries
 * both fields; the one the provider does not use is an empty string.
 */
export function useConfirmRenewal(): UseMutationResult<
  RenewalEnvelope,
  Error,
  RenewalConfirmRequest
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: RenewalConfirmRequest) =>
      api.post<RenewalEnvelope>('/me/renewal/confirm', request),
    onSuccess: (envelope) => {
      queryClient.setQueryData(RENEWAL_KEY, envelope);
    },
  });
}

/** Change the contribution renewed alongside the dues, via `PATCH /me/renewal`. */
export function useUpdateRenewal(): UseMutationResult<RenewalEnvelope, Error, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (contributionCents: number) =>
      api.patch<RenewalEnvelope>('/me/renewal', { contribution_cents: contributionCents }),
    onSuccess: (envelope) => {
      queryClient.setQueryData(RENEWAL_KEY, envelope);
    },
  });
}

/** Turn automatic renewal off, via `DELETE /me/renewal`. */
export function useCancelRenewal(): UseMutationResult<null, Error, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<null>('/me/renewal'),
    onSuccess: () => {
      queryClient.setQueryData(RENEWAL_KEY, { mandate: null } satisfies RenewalEnvelope);
    },
  });
}
