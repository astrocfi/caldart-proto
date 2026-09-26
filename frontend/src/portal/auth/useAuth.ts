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
  EmailVerifyResult,
  LoginPayload,
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

/**
 * Signs in against `POST /auth/login`, drops every query cached for whoever was here
 * before, and seeds the auth-me cache with the result.
 */
export function useLogin(): UseMutationResult<User, Error, LoginPayload> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LoginPayload) => api.post<User>('/auth/login', payload),
    onSuccess: (user) => {
      // Anything cached belonged to whoever was here before.
      queryClient.clear();
      queryClient.setQueryData(AUTH_ME_KEY, user);
    },
  });
}

/**
 * What `POST /auth/register` answers: the new account's user payload, signed in (201),
 * or, for an address that belongs to a donor, only word that a verification message
 * went there (202), with nobody signed in until the link is followed.
 */
export type RegisterResult = User | VerificationSentResult;

/** True when registering mailed a donor's address instead of signing anybody in. */
export function isVerificationSent(result: RegisterResult): result is VerificationSentResult {
  return !('id' in result);
}

/**
 * Registers against `POST /auth/register`.  When an account was created and signed
 * in, it drops every query cached for whoever was here before and seeds the auth-me
 * cache with the new user; when the address belonged to a donor, nobody is signed in
 * and the cache is left alone.
 */
export function useRegister(): UseMutationResult<RegisterResult, Error, RegisterPayload> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RegisterPayload) =>
      api.post<RegisterResult>('/auth/register', payload),
    onSuccess: (result) => {
      if (isVerificationSent(result)) return;
      queryClient.clear();
      queryClient.setQueryData(AUTH_ME_KEY, result);
    },
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
 * sign-in page renders with nothing of the old session left behind.  A call the
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
export function useEmailVerify(): UseMutationResult<EmailVerifyResult, Error, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (token: string) => api.post<EmailVerifyResult>('/auth/email/verify', { token }),
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
 * Changes the signed-in user's address through `POST /auth/email/change` and seeds
 * the auth-me cache with the answer, whose address is unverified.
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
