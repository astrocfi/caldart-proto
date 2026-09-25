/**
 * Everything the member's own Payments screen says to the API.
 *
 * The payment rows themselves come from `@/portal/features/profile/api`, which
 * already owns `GET /me/payments`, and the mandate itself from
 * `@/portal/api/queries`, which the dashboard reads too; this module adds the
 * calls that change the mandate, the contribution statements, and the two
 * download addresses.
 *
 * Every mutation writes the mandate it was answered with straight into the
 * renewal query, so the card redraws from the server's own view of the
 * authority rather than from a guess made in the browser.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { API_BASE, api } from '@/portal/api/client';
import { RENEWAL_KEY } from '@/portal/api/queries';
import type {
  MandateProvider,
  RenewalConfirmRequest,
  RenewalEnvelope,
  RenewalPatchRequest,
  RenewalSetupRequest,
  RenewalSetupResponse,
  StatementYears,
} from '@/portal/api/types';

export const STATEMENT_YEARS_KEY = ['me', 'payments', 'statements'] as const;

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
 * The setup body for a plan that may be absent.
 *
 * A life member names no plan at all, and the field is left out rather than
 * sent as null: their authority is over the contribution alone.
 */
export function renewalSetupRequest(
  plan: string | null,
  contributionCents: number,
  provider: MandateProvider,
): RenewalSetupRequest {
  const request: RenewalSetupRequest = { contribution_cents: contributionCents, provider };
  if (plan !== null) request.plan = plan;
  return request;
}

/**
 * Start saving a payment method, via `POST /me/renewal/setup`.
 *
 * The answer carries whatever the chosen provider's browser SDK needs: a Stripe
 * SetupIntent secret, a PayPal vault setup token, or nothing at all for the mock
 * provider.  Nothing is charged, and the mandate stays `pending` until it is
 * confirmed.
 *
 * Pass `signal` to abandon the attempt.  One that fires before `fetch`
 * dispatches, as an effect cleanup run straight after setup does, stops the
 * request outright, so a StrictMode remount asks the provider for one session
 * rather than two.
 */
export function startRenewalSetup(
  request: RenewalSetupRequest,
  signal?: AbortSignal,
): Promise<RenewalSetupResponse> {
  return api.post<RenewalSetupResponse>('/me/renewal/setup', request, { signal });
}

/** {@link startRenewalSetup} as a mutation, for a panel that starts on a click. */
export function useStartRenewalSetup(): UseMutationResult<
  RenewalSetupResponse,
  Error,
  RenewalSetupRequest
> {
  return useMutation({ mutationFn: (request: RenewalSetupRequest) => startRenewalSetup(request) });
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

/** Change the plan that renews and the contribution beside it, via `PATCH /me/renewal`. */
export function useUpdateRenewal(): UseMutationResult<RenewalEnvelope, Error, RenewalPatchRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: RenewalPatchRequest) =>
      api.patch<RenewalEnvelope>('/me/renewal', request),
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
