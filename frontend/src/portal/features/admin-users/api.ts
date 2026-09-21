/** Data access for the users-admin screens. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '../../api/client';
import type {
  AdminUserPatch,
  Paginated,
  RoleSlug,
  SendPasswordResetResult,
  User,
} from '../../api/types';
import { AUTH_ME_KEY } from '../../auth/useAuth';

export interface AdminUserFilters {
  search?: string;
  role?: RoleSlug | '';
  /** `''` means "any"; the API takes a real boolean. */
  is_active?: 'true' | 'false' | '';
  page?: number;
}

export const ADMIN_USERS_KEY = ['admin', 'users'] as const;

export function adminUsersKey(filters: AdminUserFilters) {
  return [...ADMIN_USERS_KEY, filters] as const;
}

export function adminUserKey(id: number | string) {
  return [...ADMIN_USERS_KEY, 'detail', String(id)] as const;
}

export function useAdminUsers(filters: AdminUserFilters) {
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

export function useAdminUser(id: string | number) {
  return useQuery({
    queryKey: adminUserKey(id),
    queryFn: () => api.get<User>(`/admin/users/${id}`),
  });
}

export function useUpdateAdminUser(id: string | number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: AdminUserPatch) => api.patch<User>(`/admin/users/${id}`, patch),
    onSuccess: (user) => {
      queryClient.setQueryData(adminUserKey(id), user);
      void queryClient.invalidateQueries({ queryKey: ADMIN_USERS_KEY });
      // Editing your own roles changes what the nav may show.
      void queryClient.invalidateQueries({ queryKey: AUTH_ME_KEY });
    },
  });
}

export function useSendPasswordReset(id: string | number) {
  return useMutation({
    mutationFn: () => api.post<SendPasswordResetResult>(`/admin/users/${id}/send-password-reset`),
  });
}
