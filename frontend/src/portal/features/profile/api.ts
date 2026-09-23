/**
 * Data access for the signed-in member's own profile, membership, and payments.
 *
 * The query keys live here and every mutation invalidates the ones it can
 * have changed — including `['auth','me']`, because saving a profile moves
 * `profile_complete` and paying moves `membership`. Queries more than one
 * feature reads, such as the plan catalog and the DART list, live in
 * `@/portal/api/queries` instead.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type {
  AttachedAircraft,
  MembershipDetail,
  PaymentSummary,
  Profile,
  ProfilePatch,
} from '@/portal/api/types';
import { AUTH_ME_KEY } from '@/portal/auth/useAuth';

export const PROFILE_KEY = ['me', 'profile'] as const;
export const MEMBERSHIP_KEY = ['me', 'membership'] as const;
export const PAYMENTS_KEY = ['me', 'payments'] as const;

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

/**
 * Saves the signed-in member's profile, writes the response into the profile cache and
 * invalidates the `auth/me` query.
 */
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
