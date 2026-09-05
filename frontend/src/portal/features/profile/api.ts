/**
 * Data access for member self-service (PLAN §6.3, §6.5).
 *
 * The join wizard, the dashboard and the profile editor all read the same
 * three resources, so the query keys live here and every mutation invalidates
 * the ones it can have changed — including `['auth','me']`, because saving a
 * profile moves `profile_complete` and paying moves `membership`.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';

import { api } from '../../api/client';
import { AUTH_ME_KEY } from '../../auth/useAuth';
import type {
  AircraftSummary,
  Dart,
  MembershipDetail,
  PaymentSummary,
  Plan,
  Profile,
  ProfilePatch,
  SiteConfig,
} from '../../api/types';

export const PROFILE_KEY = ['me', 'profile'] as const;
export const MEMBERSHIP_KEY = ['me', 'membership'] as const;
export const PAYMENTS_KEY = ['me', 'payments'] as const;
export const DARTS_KEY = ['darts'] as const;
export const PLANS_KEY = ['plans'] as const;
export const SITE_CONFIG_KEY = ['site', 'config'] as const;

/** `POST /me/profile/aircraft` and its DELETE both answer with the new list. */
export interface AttachedAircraft {
  aircraft: AircraftSummary[];
}

export function useProfile(): UseQueryResult<Profile> {
  return useQuery({ queryKey: PROFILE_KEY, queryFn: () => api.get<Profile>('/me/profile') });
}

export function useMembership(): UseQueryResult<MembershipDetail> {
  return useQuery({
    queryKey: MEMBERSHIP_KEY,
    queryFn: () => api.get<MembershipDetail>('/me/membership'),
  });
}

export function useMyPayments(): UseQueryResult<PaymentSummary[]> {
  return useQuery({
    queryKey: PAYMENTS_KEY,
    queryFn: () => api.get<PaymentSummary[]>('/me/payments'),
  });
}

/** Public: the join wizard reads it before the visitor has an account. */
export function useDarts(): UseQueryResult<Dart[]> {
  return useQuery({
    queryKey: DARTS_KEY,
    queryFn: () => api.get<Dart[]>('/darts'),
    staleTime: 5 * 60_000,
  });
}

/** Public: the plan catalogue shown on the pay step. */
export function usePlans(): UseQueryResult<Plan[]> {
  return useQuery({
    queryKey: PLANS_KEY,
    queryFn: () => api.get<Plan[]>('/plans'),
    staleTime: 5 * 60_000,
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

export function useSaveProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: ProfilePatch) => api.put<Profile>('/me/profile', patch),
    onSuccess: (profile) => {
      queryClient.setQueryData(PROFILE_KEY, profile);
      // `profile_complete` lives on the user payload.
      void queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
    },
  });
}

export function useAttachAircraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (aircraftId: number) =>
      api.post<AttachedAircraft>('/me/profile/aircraft', { aircraft_id: aircraftId }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: PROFILE_KEY }),
  });
}

export function useDetachAircraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (aircraftId: number) => api.delete<null>(`/me/profile/aircraft/${aircraftId}`),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: PROFILE_KEY }),
  });
}
