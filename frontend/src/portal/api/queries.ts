/**
 * Read-only queries shared by more than one feature.
 *
 * `useDarts`, `usePlans`, `useSiteConfig`, `useRenewal`, and `useDonation` back
 * screens across several features (the join wizard, the dashboard, the payments
 * screen, the checkout, and administration screens), so they live here rather than
 * inside any one feature's `api.ts`.
 */
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type { Dart, Plan, RenewalEnvelope, SiteConfig } from '@/portal/api/types';

export const DARTS_KEY = ['darts'] as const;
export const PLANS_KEY = ['plans'] as const;
export const SITE_CONFIG_KEY = ['site', 'config'] as const;
export const RENEWAL_KEY = ['me', 'renewal'] as const;
export const DONATION_KEY = ['me', 'donation'] as const;

/** Public: the join wizard reads it before the visitor has an account. */
export function useDarts(): UseQueryResult<Dart[]> {
  return useQuery({
    queryKey: DARTS_KEY,
    queryFn: () => api.get<Dart[]>('/darts'),
    staleTime: 5 * 60_000,
  });
}

/** Public: the plan catalog shown on the pay step. */
export function usePlans(): UseQueryResult<Plan[]> {
  return useQuery({
    queryKey: PLANS_KEY,
    queryFn: () => api.get<Plan[]>('/plans'),
    staleTime: 5 * 60_000,
  });
}

/** Which of a person's two standing authorities: the renewal or the recurring donation. */
export type MandateScope = 'renewal' | 'donation';

/** Where each scope's singleton lives under `/api/v1`. */
export const MANDATE_PATHS: Record<MandateScope, string> = {
  renewal: '/me/renewal',
  donation: '/me/donation',
};

/** The query key each scope's mandate is cached under. */
export function mandateKey(scope: MandateScope): typeof RENEWAL_KEY | typeof DONATION_KEY {
  return scope === 'donation' ? DONATION_KEY : RENEWAL_KEY;
}

/**
 * The signed-in person's automatic renewal or recurring donation, via `GET
 * /me/renewal` or `GET /me/donation`.  `enabled` holds the request back while it is
 * false.
 */
export function useMandate(
  scope: MandateScope,
  { enabled = true }: { enabled?: boolean } = {},
): UseQueryResult<RenewalEnvelope> {
  return useQuery({
    queryKey: mandateKey(scope),
    queryFn: () => api.get<RenewalEnvelope>(MANDATE_PATHS[scope]),
    enabled,
  });
}

/**
 * The signed-in member's standing authority to renew, via `GET /me/renewal`.
 *
 * The dashboard states it in a line and the Payments screen states it in full,
 * so both read it from here; the checkout reads it only while a contribution is
 * being given, which `enabled` says.
 */
export function useRenewal(options: { enabled?: boolean } = {}): UseQueryResult<RenewalEnvelope> {
  return useMandate('renewal', options);
}

/**
 * The signed-in person's recurring donation, via `GET /me/donation`.
 *
 * The Payments screen states it and the dashboard names a life member's.
 */
export function useDonation(): UseQueryResult<RenewalEnvelope> {
  return useMandate('donation');
}

/** Site chrome, read for the members-only page list on the dashboard. */
export function useSiteConfig(): UseQueryResult<SiteConfig> {
  return useQuery({
    queryKey: SITE_CONFIG_KEY,
    queryFn: () => api.get<SiteConfig>('/site/config'),
    staleTime: 5 * 60_000,
  });
}
