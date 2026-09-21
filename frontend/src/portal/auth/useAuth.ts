/**
 * Auth state for the portal, backed by `GET /auth/me` through TanStack Query.
 *
 * The query key `['auth', 'me']` is the contract everything else invalidates:
 * anything that can change who you are, or what they may do, writes it or
 * invalidates it here rather than in a page.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { ApiError, api } from '../api/client';
import type {
  LoginPayload,
  PasswordChangePayload,
  PasswordResetConfirmPayload,
  PasswordResetRequestPayload,
  RegisterPayload,
  Role,
  RoleSlug,
  User,
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

/** Signs in against `POST /auth/login` and seeds the auth-me cache with the result. */
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

/** Registers against `POST /auth/register` and seeds the auth-me cache with the result. */
export function useRegister(): UseMutationResult<User, Error, RegisterPayload> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RegisterPayload) => api.post<User>('/auth/register', payload),
    onSuccess: (user) => {
      queryClient.clear();
      queryClient.setQueryData(AUTH_ME_KEY, user);
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
