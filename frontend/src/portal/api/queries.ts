/**
 * Read-only queries shared by more than one feature.
 *
 * `useDarts`, `usePlans`, `useSiteConfig`, and `useRenewal` back screens across
 * several features (the join wizard, the dashboard, the payments screen, and
 * administration screens), so they live here rather than inside any one
 * feature's `api.ts`.
 */
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type { Dart, Plan, RenewalEnvelope, SiteConfig } from '@/portal/api/types';

export const DARTS_KEY = ['darts'] as const;
export const PLANS_KEY = ['plans'] as const;
export const SITE_CONFIG_KEY = ['site', 'config'] as const;
export const RENEWAL_KEY = ['me', 'renewal'] as const;

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

/**
 * The signed-in member's standing authority to renew, via `GET /me/renewal`.
 *
 * The dashboard states it in a line and the Payments screen states it in full,
 * so both read it from here.
 */
export function useRenewal(): UseQueryResult<RenewalEnvelope> {
  return useQuery({
    queryKey: RENEWAL_KEY,
    queryFn: () => api.get<RenewalEnvelope>('/me/renewal'),
  });
}

/** Site chrome, read for the members-only page list on the dashboard. */
export function useSiteConfig(): UseQueryResult<SiteConfig> {
  return useQuery({
    queryKey: SITE_CONFIG_KEY,
    queryFn: () => api.get<SiteConfig>('/site/config'),
    staleTime: 5 * 60_000,
  });
}
