/**
 * Auth state for the portal, backed by `GET /auth/me` through TanStack Query.
 *
 * The query key `['auth', 'me']` is the contract everything else invalidates:
 * anything that can change who you are, or what they may do, writes it or
 * invalidates it here rather than in a page.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

import { ApiError, api } from '../api/client';
import type {
  EmailChangePayload,
  EmailChangeUndoPayload,
  EmailChangeUndoResult,
  EmailVerifyPayload,
  EmailVerifyResult,
  EnrolledSignIn,
  LoginPayload,
  LoginResult,
  MfaChallenge,
  MfaEnrollment,
  OtpPayload,
  PasswordChangePayload,
  PasswordResetConfirmPayload,
  PasswordResetRequestPayload,
  RegisterPayload,
  Role,
  RoleSlug,
  User,
  VerificationSentResult,
} from '../api/types';

export const AUTH_ME_KEY = ['auth', 'me'] as const;
export const ROLES_KEY = ['auth', 'roles'] as const;

/** Fetch the signed-in user from `GET /auth/me`, or `null` for an anonymous visitor. */
export async function fetchMe(): Promise<User | null> {
  try {
    return await api.get<User>('/auth/me');
  } catch (error) {
    if (error instanceof ApiError && error.isUnauthenticated) return null;
    throw error;
  }
}

/**
 * The raw `GET /auth/me` query, for callers that want its status flags.
 *
 * It takes the app-wide retry policy, so a 5xx or a dropped connection is
 * retried before anything reacts to it.  A 401 resolves to `null` rather than
 * throwing, so signing out is still instant.
 */
export function useMe(): UseQueryResult<User | null> {
  return useQuery({
    queryKey: AUTH_ME_KEY,
    queryFn: fetchMe,
    staleTime: 30_000,
  });
}

export interface AuthState {
  user: User | null;
  roles: RoleSlug[];
  isLoading: boolean;
  isAuthenticated: boolean;
  /** A refetch is in flight over a result that is already cached. */
  isRefetching: boolean;
  /** Set when the check failed outright; a 401 is not an error. */
  error: unknown;
  /** Ask `GET /auth/me` again, for a "Try again" control. */
  refetch: () => void;
}

/** The flattened view most screens want. */
export function useAuth(): AuthState {
  const query = useMe();
  const user = query.data ?? null;
  return {
    user,
    roles: user?.roles ?? [],
    isLoading: query.isPending,
    isAuthenticated: user !== null,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: () => {
      void query.refetch();
    },
  };
}

/** The role catalog from `GET /roles`, for the users-admin screens. */
export function useRoles(): UseQueryResult<Role[]> {
  return useQuery({
    queryKey: ROLES_KEY,
    queryFn: () => api.get<Role[]>('/roles'),
    staleTime: 5 * 60_000,
  });
}

/** True when signing in still needs a second factor rather than having signed in. */
export function isMfaChallenge(result: LoginResult): result is MfaChallenge {
  return 'mfa' in result;
}

/**
 * Starts the portal afresh for `user`, who has just signed in: drops every query cached
 * for whoever was here before, and seeds the auth-me cache with the account.
 */
export function useAdoptSignedIn(): (user: User) => void {
  const queryClient = useQueryClient();
  return (user: User) => {
    queryClient.clear();
    queryClient.setQueryData(AUTH_ME_KEY, user);
  };
}

/**
 * Posts credentials to `path`, which answers with the user it signed in or with the
 * second factor still owed; a signed-in user starts a fresh cache.
 */
function useCredentialsSignIn(path: string): UseMutationResult<LoginResult, Error, LoginPayload> {
  const adopt = useAdoptSignedIn();
  return useMutation({
    mutationFn: (payload: LoginPayload) => api.post<LoginResult>(path, payload),
    onSuccess: (result) => {
      if (!isMfaChallenge(result)) adopt(result);
    },
  });
}

/** Signs in against `POST /auth/login`, starting a fresh cache for that user. */
export function useLogin(): UseMutationResult<LoginResult, Error, LoginPayload> {
  return useCredentialsSignIn('/auth/login');
}

/**
 * Brings a deactivated account back through `POST /auth/reactivate`, with the same
 * email address and password a sign-in takes, and signs it in as `useLogin` does.
 */
export function useReactivate(): UseMutationResult<LoginResult, Error, LoginPayload> {
  return useCredentialsSignIn('/auth/reactivate');
}

/** Finishes a sign-in with a code through `POST /auth/login/mfa`, starting a fresh cache. */
export function useLoginMfa(): UseMutationResult<User, Error, OtpPayload> {
  const adopt = useAdoptSignedIn();
  return useMutation({
    mutationFn: (payload: OtpPayload) => api.post<User>('/auth/login/mfa', payload),
    onSuccess: adopt,
  });
}

/** Starts setting up a device while signing in, through `POST /auth/login/mfa/enroll`. */
export function useLoginMfaEnroll(): UseMutationResult<MfaEnrollment, Error, void> {
  return useMutation({
    mutationFn: () => api.post<MfaEnrollment>('/auth/login/mfa/enroll'),
  });
}

/**
 * Confirms the new device and signs in through `POST /auth/login/mfa/enroll/confirm`.
 *
 * The cache is left alone: the sign-in screen shows the backup codes first, and adopts
 * the user (`useAdoptSignedIn`) once the person says they saved them.
 */
export function useLoginMfaEnrollConfirm(): UseMutationResult<EnrolledSignIn, Error, OtpPayload> {
  return useMutation({
    mutationFn: (payload: OtpPayload) =>
      api.post<EnrolledSignIn>('/auth/login/mfa/enroll/confirm', payload),
  });
}

/**
 * Registers against `POST /auth/register`.  The server answers every address the same
 * way, with a sentence naming it, and doesn't sign anyone in: the address's owner learns the
 * next step from the message mailed there.  The cache is left alone.
 */
export function useRegister(): UseMutationResult<VerificationSentResult, Error, RegisterPayload> {
  return useMutation({
    mutationFn: (payload: RegisterPayload) =>
      api.post<VerificationSentResult>('/auth/register', payload),
  });
}

/** Signs out against `POST /auth/logout` and clears every cached query. */
export function useLogout(): UseMutationResult<null, Error, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<null>('/auth/logout'),
    onSuccess: () => {
      // Drop every cached page: none of it is this browser's business now.
      queryClient.clear();
      queryClient.setQueryData(AUTH_ME_KEY, null);
    },
  });
}

export interface SignOut {
  /** End the session, then go to the sign-in page. */
  signOut: () => void;
  /** The `POST /auth/logout` call is in flight. */
  isPending: boolean;
}

/**
 * The portal's sign-out control: end the session, then land on `/login`.
 *
 * Signing out is a `POST` a person presses, so no address ends a session by being
 * opened.  `useLogout` empties the query cache before the navigation runs, so the
 * sign-in page renders without any trace of the old session.  A call the
 * server refuses leaves the member where they were, with the control usable again.
 */
export function useSignOut(): SignOut {
  const logout = useLogout();
  const navigate = useNavigate();

  return {
    signOut: () => {
      logout.mutate(undefined, {
        onSuccess: () => {
          void navigate('/login', { replace: true });
        },
      });
    },
    isPending: logout.isPending,
  };
}

/** Changes the signed-in user's password through `POST /auth/password/change`. */
export function usePasswordChange(): UseMutationResult<null, Error, PasswordChangePayload> {
  return useMutation({
    mutationFn: (payload: PasswordChangePayload) =>
      api.post<null>('/auth/password/change', payload),
  });
}

/** Requests a password-reset email through `POST /auth/password/reset`. */
export function usePasswordResetRequest(): UseMutationResult<
  null,
  Error,
  PasswordResetRequestPayload
> {
  return useMutation({
    mutationFn: (payload: PasswordResetRequestPayload) =>
      api.post<null>('/auth/password/reset', payload),
  });
}

/** Completes a password reset through `POST /auth/password/reset/confirm`. */
export function usePasswordResetConfirm(): UseMutationResult<
  null,
  Error,
  PasswordResetConfirmPayload
> {
  return useMutation({
    mutationFn: (payload: PasswordResetConfirmPayload) =>
      api.post<null>('/auth/password/reset/confirm', payload),
  });
}

/**
 * Follows a verification link through `POST /auth/email/verify`, then asks
 * `/auth/me` again before the mutation settles, so a signed-in visitor's own
 * payload already says verified when the page shows the result.
 */
export function useEmailVerify(): UseMutationResult<EmailVerifyResult, Error, EmailVerifyPayload> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: EmailVerifyPayload) =>
      api.post<EmailVerifyResult>('/auth/email/verify', payload),
    onSuccess: async () => {
      // The page opens with its first `/auth/me` in flight, and the server may
      // have read the account before the verification committed.  Invalidating
      // alone would join that request rather than replace it, so cancel it first.
      await queryClient.cancelQueries({ queryKey: AUTH_ME_KEY });
      await queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
    },
  });
}

/** Mails the signed-in user a fresh verification link through `POST /auth/email/resend`. */
export function useResendVerification(): UseMutationResult<VerificationSentResult, Error, void> {
  return useMutation({
    mutationFn: () => api.post<VerificationSentResult>('/auth/email/resend'),
  });
}

/**
 * Asks to change the signed-in user's address through `POST /auth/email/change` and
 * seeds the auth-me cache with the answer: `email` is still the sign-in address, and
 * `pending_email` the address the link went to.
 */
export function useEmailChange(): UseMutationResult<User, Error, EmailChangePayload> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: EmailChangePayload) => api.post<User>('/auth/email/change', payload),
    onSuccess: (user) => {
      queryClient.setQueryData(AUTH_ME_KEY, user);
    },
  });
}

/**
 * Follows a link that undoes a change of address through `POST /auth/email/undo`.  The
 * server ends every session of the account, so on success the cache is emptied and the
 * auth-me cache reads as signed out.
 */
export function useEmailChangeUndo(): UseMutationResult<
  EmailChangeUndoResult,
  Error,
  EmailChangeUndoPayload
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: EmailChangeUndoPayload) =>
      api.post<EmailChangeUndoResult>('/auth/email/undo', payload),
    onSuccess: () => {
      queryClient.clear();
      queryClient.setQueryData(AUTH_ME_KEY, null);
    },
  });
}
