/**
 * Auth state for the portal, backed by `GET /auth/me` through TanStack Query.
 *
 * The query key `['auth', 'me']` is the contract everything else invalidates:
 * anything that can change who you are, or what they may do, writes it or
 * invalidates it here rather than in a page.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';

import { ApiError, api } from '../api/client';
import type {
  LoginPayload,
  PasswordChangePayload,
  PasswordResetConfirmPayload,
  RegisterPayload,
  Role,
  RoleSlug,
  User,
} from '../api/types';

export const AUTH_ME_KEY = ['auth', 'me'] as const;
export const ROLES_KEY = ['auth', 'roles'] as const;

export interface PasswordResetRequestPayload {
  email: string;
}

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
export function useRoles() {
  return useQuery({
    queryKey: ROLES_KEY,
    queryFn: () => api.get<Role[]>('/roles'),
    staleTime: 5 * 60_000,
  });
}

export function useLogin() {
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

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: RegisterPayload) => api.post<User>('/auth/register', payload),
    onSuccess: (user) => {
      queryClient.clear();
      queryClient.setQueryData(AUTH_ME_KEY, user);
    },
  });
}

export function useLogout() {
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

export function usePasswordChange() {
  return useMutation({
    mutationFn: (payload: PasswordChangePayload) =>
      api.post<null>('/auth/password/change', payload),
  });
}

export function usePasswordResetRequest() {
  return useMutation({
    mutationFn: (payload: PasswordResetRequestPayload) =>
      api.post<null>('/auth/password/reset', payload),
  });
}

export function usePasswordResetConfirm() {
  return useMutation({
    mutationFn: (payload: PasswordResetConfirmPayload) =>
      api.post<null>('/auth/password/reset/confirm', payload),
  });
}
