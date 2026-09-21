/**
 * Data access for member self-service.
 *
 * The join wizard, the dashboard and the profile editor all read the same
 * three resources, so the query keys live here and every mutation invalidates
 * the ones it can have changed — including `['auth','me']`, because saving a
 * profile moves `profile_complete` and paying moves `membership`.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '../../api/client';
import { AUTH_ME_KEY } from '../../auth/useAuth';
import type {
  AttachedAircraft,
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

/** The signed-in member's own profile, via `GET /me/profile`. */
export function useProfile(): UseQueryResult<Profile> {
  return useQuery({ queryKey: PROFILE_KEY, queryFn: () => api.get<Profile>('/me/profile') });
}

/** The signed-in member's membership status, via `GET /me/membership`. */
export function useMembership(): UseQueryResult<MembershipDetail> {
  return useQuery({
    queryKey: MEMBERSHIP_KEY,
    queryFn: () => api.get<MembershipDetail>('/me/membership'),
  });
}

/** The signed-in member's payment history, via `GET /me/payments`. */
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

/** Public: the plan catalog shown on the pay step. */
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

/** Saves the signed-in member's profile and invalidates the profile and `auth/me` queries. */
export function useSaveProfile(): UseMutationResult<Profile, Error, ProfilePatch> {
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

/** Attaches an aircraft to the signed-in member's profile and invalidates it. */
export function useAttachAircraft(): UseMutationResult<AttachedAircraft, Error, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (aircraftId: number) =>
      api.post<AttachedAircraft>('/me/profile/aircraft', { aircraft_id: aircraftId }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: PROFILE_KEY }),
  });
}

/** Detaches an aircraft from the signed-in member's profile and invalidates it. */
export function useDetachAircraft(): UseMutationResult<null, Error, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (aircraftId: number) => api.delete<null>(`/me/profile/aircraft/${aircraftId}`),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: PROFILE_KEY }),
  });
}
