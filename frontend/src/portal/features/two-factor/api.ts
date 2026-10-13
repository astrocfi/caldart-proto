/**
 * The signed-in person's own two-factor sign-in: `GET /auth/mfa` and the actions on the
 * profile's **Two-factor sign-in** card.  The sign-in steps live in `auth/useAuth.ts`.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type {
  MfaDisablePayload,
  MfaEnrollPayload,
  MfaEnrollment,
  MfaStatus,
  OtpPayload,
  RecoveryCodes,
} from '@/portal/api/types';

export const MFA_STATUS_KEY = ['auth', 'mfa'] as const;

/** Whether two-factor sign-in is on, whether a role requires it, and the codes left. */
export function useMfaStatus(): UseQueryResult<MfaStatus> {
  return useQuery({ queryKey: MFA_STATUS_KEY, queryFn: () => api.get<MfaStatus>('/auth/mfa') });
}

/** Starts turning two-factor sign-in on, given the password: `POST /auth/mfa/enroll`. */
export function useStartMfaEnrollment(): UseMutationResult<MfaEnrollment, Error, MfaEnrollPayload> {
  return useMutation({
    mutationFn: (payload: MfaEnrollPayload) => api.post<MfaEnrollment>('/auth/mfa/enroll', payload),
  });
}

/**
 * A two-factor action that changes the status: once it has gone through, the status is
 * asked for again.
 */
function useStatusChanging<TResult, TPayload>(
  path: string,
): UseMutationResult<TResult, Error, TPayload> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TPayload) => api.post<TResult>(path, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: MFA_STATUS_KEY }),
  });
}

/** Confirms the new device with a code, turning it on: `POST /auth/mfa/enroll/confirm`. */
export function useConfirmMfaEnrollment(): UseMutationResult<RecoveryCodes, Error, OtpPayload> {
  return useStatusChanging<RecoveryCodes, OtpPayload>('/auth/mfa/enroll/confirm');
}

/** Replaces every backup code, given a current code: `POST /auth/mfa/recovery-codes`. */
export function useRegenerateRecoveryCodes(): UseMutationResult<RecoveryCodes, Error, OtpPayload> {
  return useStatusChanging<RecoveryCodes, OtpPayload>('/auth/mfa/recovery-codes');
}

/** Turns two-factor sign-in off with the password and a code: `POST /auth/mfa/disable`. */
export function useDisableMfa(): UseMutationResult<null, Error, MfaDisablePayload> {
  return useStatusChanging<null, MfaDisablePayload>('/auth/mfa/disable');
}
