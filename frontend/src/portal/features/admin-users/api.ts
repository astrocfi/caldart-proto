/** Data access for the users-admin screens. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type {
  AdminUser,
  AdminUserPatch,
  Paginated,
  RoleSlug,
  SendPasswordResetResult,
  User,
  VerificationSentResult,
} from '@/portal/api/types';
import { AUTH_ME_KEY } from '@/portal/auth/useAuth';

export interface AdminUserFilters {
  search?: string;
  role?: RoleSlug | '';
  /** `''` means "any"; the API takes a real boolean. */
  is_active?: 'true' | 'false' | '';
  page?: number;
}

export const ADMIN_USERS_KEY = ['admin', 'users'] as const;

/** The query key for a filtered users list. */
export function adminUsersKey(
  filters: AdminUserFilters,
): readonly [...typeof ADMIN_USERS_KEY, AdminUserFilters] {
  return [...ADMIN_USERS_KEY, filters] as const;
}

/** The query key for one account's detail. */
export function adminUserKey(
  id: number | string,
): readonly [...typeof ADMIN_USERS_KEY, 'detail', string] {
  return [...ADMIN_USERS_KEY, 'detail', String(id)] as const;
}

/** The paginated account list for `/admin/users`, filtered, and paged. */
export function useAdminUsers(filters: AdminUserFilters): UseQueryResult<Paginated<User>> {
  return useQuery({
    queryKey: adminUsersKey(filters),
    queryFn: () =>
      api.get<Paginated<User>>('/admin/users', {
        query: {
          search: filters.search,
          role: filters.role,
          is_active: filters.is_active,
          page: filters.page && filters.page > 1 ? filters.page : undefined,
        },
      }),
    placeholderData: (previous) => previous,
  });
}

/** One account's detail record by id, including when its email address was verified. */
export function useAdminUser(id: string | number): UseQueryResult<AdminUser> {
  return useQuery({
    queryKey: adminUserKey(id),
    queryFn: () => api.get<AdminUser>(`/admin/users/${id}`),
  });
}

/**
 * Patches one account's names, email, roles, or status.
 *
 * Also invalidates the signed-in caller's own `auth/me` query, since editing
 * your own roles changes what the nav may show.
 */
export function useUpdateAdminUser(
  id: string | number,
): UseMutationResult<AdminUser, Error, AdminUserPatch> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: AdminUserPatch) => api.patch<AdminUser>(`/admin/users/${id}`, patch),
    onSuccess: (user) => {
      queryClient.setQueryData(adminUserKey(id), user);
      void queryClient.invalidateQueries({ queryKey: ADMIN_USERS_KEY });
      // Editing your own roles changes what the nav may show.
      void queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
    },
  });
}

/** Sends the account a password-reset email. */
export function useSendPasswordReset(
  id: string | number,
): UseMutationResult<SendPasswordResetResult, Error, void> {
  return useMutation({
    mutationFn: () => api.post<SendPasswordResetResult>(`/admin/users/${id}/send-password-reset`),
  });
}

/** Mails the account a fresh verification link for its current address. */
export function useSendEmailVerification(
  id: string | number,
): UseMutationResult<VerificationSentResult, Error, void> {
  return useMutation({
    mutationFn: () =>
      api.post<VerificationSentResult>(`/admin/users/${id}/send-email-verification`),
  });
}
