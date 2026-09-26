/**
 * Everything the member's own Payments screen says to the API.
 *
 * The payment rows themselves come from `@/portal/features/profile/api`, which
 * already owns `GET /me/payments`, and the mandate itself from
 * `@/portal/api/queries`, which the dashboard reads too; this module adds the
 * calls that change the mandate, the contribution statements, and the two
 * download addresses.
 *
 * A person holds at most one automatic renewal and one recurring donation, and
 * the two live at `/me/renewal` and `/me/donation`; every call here takes the
 * {@link MandateScope} it is about.  Every mutation writes the mandate it was
 * answered with straight into that scope's query, so the card redraws from the
 * server's own view of the authority rather than from a guess made in the
 * browser.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { API_BASE, api } from '@/portal/api/client';
import { MANDATE_PATHS, mandateKey } from '@/portal/api/queries';
import type { MandateScope } from '@/portal/api/queries';
import type {
  IsoDate,
  MandateCadence,
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

/** What a provider panel was handed, as the setup body it sends. */
export interface RenewalSetupFields {
  /** The plan that renews, or null for a recurring donation. */
  plan: string | null;
  contributionCents: number;
  provider: MandateProvider;
  /** The day of the first charge, which the member chose. */
  nextChargeOn: IsoDate;
  /** How often a recurring donation charges; left out for a renewal. */
  cadence?: MandateCadence;
  /** The member agreed to move their renewal's contribution to this donation. */
  removeRenewalContribution?: boolean;
}

/**
 * The setup body for a plan that may be absent.
 *
 * A donation names no plan at all, and the field is left out rather than sent as
 * null.  `cadence` and `remove_renewal_contribution` travel only when they say
 * something: the server's defaults are a yearly authority and no move.
 */
export function renewalSetupRequest({
  plan,
  contributionCents,
  provider,
  nextChargeOn,
  cadence,
  removeRenewalContribution = false,
}: RenewalSetupFields): RenewalSetupRequest {
  const request: RenewalSetupRequest = {
    contribution_cents: contributionCents,
    provider,
    next_charge_on: nextChargeOn,
  };
  if (plan !== null) request.plan = plan;
  if (cadence !== undefined) request.cadence = cadence;
  if (removeRenewalContribution) request.remove_renewal_contribution = true;
  return request;
}

/**
 * Start saving a payment method, via `POST /me/renewal/setup` or `/me/donation/setup`.
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
  scope: MandateScope,
  request: RenewalSetupRequest,
  signal?: AbortSignal,
): Promise<RenewalSetupResponse> {
  return api.post<RenewalSetupResponse>(`${MANDATE_PATHS[scope]}/setup`, request, { signal });
}

/** {@link startRenewalSetup} as a mutation, for a panel that starts on a click. */
export function useStartRenewalSetup(
  scope: MandateScope,
): UseMutationResult<RenewalSetupResponse, Error, RenewalSetupRequest> {
  return useMutation({
    mutationFn: (request: RenewalSetupRequest) => startRenewalSetup(scope, request),
  });
}

/**
 * Save the method the browser collected and make the mandate active, via
 * `POST /me/renewal/confirm` or `/me/donation/confirm`.
 *
 * Both provider references travel on every request because the body carries
 * both fields; the one the provider does not use is an empty string.
 */
export function useConfirmRenewal(
  scope: MandateScope,
): UseMutationResult<RenewalEnvelope, Error, RenewalConfirmRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: RenewalConfirmRequest) =>
      api.post<RenewalEnvelope>(`${MANDATE_PATHS[scope]}/confirm`, request),
    onSuccess: (envelope) => {
      queryClient.setQueryData(mandateKey(scope), envelope);
    },
  });
}

/**
 * Change what an authority charges, via `PATCH /me/renewal` or `/me/donation`: the
 * plan and contribution of a renewal, or the amount and cadence of a donation, and
 * the day of the next charge.
 */
export function useUpdateRenewal(
  scope: MandateScope,
): UseMutationResult<RenewalEnvelope, Error, RenewalPatchRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: RenewalPatchRequest) =>
      api.patch<RenewalEnvelope>(MANDATE_PATHS[scope], request),
    onSuccess: (envelope) => {
      queryClient.setQueryData(mandateKey(scope), envelope);
    },
  });
}

/** Turn an authority off, via `DELETE /me/renewal` or `/me/donation`. */
export function useCancelRenewal(scope: MandateScope): UseMutationResult<null, Error, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<null>(MANDATE_PATHS[scope]),
    onSuccess: () => {
      queryClient.setQueryData(mandateKey(scope), { mandate: null } satisfies RenewalEnvelope);
    },
  });
}
