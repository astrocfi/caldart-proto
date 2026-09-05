/**
 * Auth state for the portal, backed by `GET /auth/me` through TanStack Query.
 *
 * `feat/auth-portal` extends this with registration and password flows; the
 * query key `['auth', 'me']` is the contract everything else invalidates.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, api } from '../api/client';
import type { LoginPayload, RoleSlug, User } from '../api/types';

export const AUTH_ME_KEY = ['auth', 'me'] as const;

export async function fetchMe(): Promise<User | null> {
  try {
    return await api.get<User>('/auth/me');
  } catch (error) {
    if (error instanceof ApiError && error.isUnauthenticated) return null;
    throw error;
  }
}

export interface AuthState {
  user: User | null;
  roles: RoleSlug[];
  isLoading: boolean;
  isAuthenticated: boolean;
  error: unknown;
}

export function useAuth(): AuthState {
  const query = useQuery({
    queryKey: AUTH_ME_KEY,
    queryFn: fetchMe,
    staleTime: 30_000,
    retry: false,
  });

  const user = query.data ?? null;
  return {
    user,
    roles: user?.roles ?? [],
    isLoading: query.isPending,
    isAuthenticated: user !== null,
    error: query.error,
  };
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: LoginPayload) => api.post<User>('/auth/login', payload),
    onSuccess: (user) => {
      queryClient.setQueryData(AUTH_ME_KEY, user);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<null>('/auth/logout'),
    onSuccess: () => {
      queryClient.setQueryData(AUTH_ME_KEY, null);
      void queryClient.invalidateQueries();
    },
  });
}
