/**
 * The three writes of verification: a person's items, an aircraft's insurance, and the
 * verifier role.
 *
 * Every screen that shows a verified state reads it from a query this module refreshes:
 * the member check's status card, the member record, and the aircraft register.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import { AUTH_ME_KEY } from '@/portal/auth/useAuth';
import { MEMBERS_KEY } from '@/portal/features/admin-members/api';
import { AIRCRAFT_KEY } from '@/portal/features/aircraft/api';
import { LEADER_KEY } from '@/portal/features/leader/api';
import type {
  InsuranceVerificationPayload,
  MemberVerificationPayload,
  AircraftDetail,
  LeaderStatus,
  VerifierGrantPayload,
} from '@/portal/api/types';

/** Puts the returned status card in place and marks everything that shows the person stale. */
function useStatusSaved(userId: number): (status: LeaderStatus) => void {
  const queryClient = useQueryClient();
  return (status) => {
    queryClient.setQueryData([LEADER_KEY, 'status', userId], status);
    void queryClient.invalidateQueries({ queryKey: [LEADER_KEY, 'search'] });
    void queryClient.invalidateQueries({ queryKey: MEMBERS_KEY });
  };
}

/**
 * Writes a person's certificate, medical, and photo ID fields and the verified state of
 * each item in one request, via `PUT /leader/members/{userId}/verification`.
 */
export function useVerifyMember(
  userId: number,
): UseMutationResult<LeaderStatus, Error, MemberVerificationPayload> {
  const handleSaved = useStatusSaved(userId);
  return useMutation({
    mutationFn: (payload: MemberVerificationPayload) =>
      api.put<LeaderStatus>(`/leader/members/${userId}/verification`, payload),
    onSuccess: handleSaved,
  });
}

/**
 * Writes an aircraft's insurance fields and whether the insurance is verified, via
 * `PUT /leader/aircraft/{aircraftId}/verification`.
 */
export function useVerifyInsurance(
  aircraftId: number,
): UseMutationResult<AircraftDetail, Error, InsuranceVerificationPayload> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: InsuranceVerificationPayload) =>
      api.put<AircraftDetail>(`/leader/aircraft/${aircraftId}/verification`, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [LEADER_KEY] });
      void queryClient.invalidateQueries({ queryKey: [AIRCRAFT_KEY] });
    },
  });
}

/**
 * Grants or takes away the verifier role, via `PUT /leader/members/{userId}/verifier`.
 *
 * The signed-in user's own roles are read again too, since a leader may grant it to
 * themselves.
 */
export function useSetVerifier(
  userId: number,
): UseMutationResult<LeaderStatus, Error, VerifierGrantPayload> {
  const queryClient = useQueryClient();
  const handleSaved = useStatusSaved(userId);
  return useMutation({
    mutationFn: (payload: VerifierGrantPayload) =>
      api.put<LeaderStatus>(`/leader/members/${userId}/verifier`, payload),
    onSuccess: (status) => {
      handleSaved(status);
      void queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
    },
  });
}
