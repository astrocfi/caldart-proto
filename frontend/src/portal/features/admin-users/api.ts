/** Data access for the users-admin screens. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import { ADMIN_USERS_KEY } from '@/portal/api/queries';
import type {
  AccountChange,
  AccountKind,
  AdminUser,
  AdminUserDetail,
  AdminUserPatch,
  Paginated,
  RoleSlug,
  SendPasswordResetResult,
  VerificationSentResult,
} from '@/portal/api/types';
import { AUTH_ME_KEY } from '@/portal/auth/useAuth';
import { MEMBERS_KEY } from '@/portal/features/admin-members/api';
import { FINANCE_KEY } from '@/portal/features/admin-payments/api';

export interface AdminUserFilters {
  search?: string;
  role?: RoleSlug | '';
  /** `''` means "any"; the API takes a real boolean. */
  is_active?: 'true' | 'false' | '';
  /** `''` means any kind of account. */
  kind?: AccountKind | '';
  /** `'true'` for bounced addresses only, `'false'` for the rest, `''` for any. */
  email_bounced?: 'true' | 'false' | '';
  /** The `?ordering=` term, such as `last_name` or `-email`. */
  ordering?: string;
  page?: number;
}

export { ADMIN_USERS_KEY };

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
export function useAdminUsers(filters: AdminUserFilters): UseQueryResult<Paginated<AdminUser>> {
  return useQuery({
    queryKey: adminUsersKey(filters),
    queryFn: () =>
      api.get<Paginated<AdminUser>>('/admin/users', {
        query: {
          search: filters.search,
          role: filters.role,
          is_active: filters.is_active,
          kind: filters.kind,
          email_bounced: filters.email_bounced,
          ordering: filters.ordering,
          page: filters.page && filters.page > 1 ? filters.page : undefined,
        },
      }),
    placeholderData: (previous) => previous,
  });
}

/** One account's detail record by id, including when its email address was verified. */
export function useAdminUser(id: string | number): UseQueryResult<AdminUserDetail> {
  return useQuery({
    queryKey: adminUserKey(id),
    queryFn: () => api.get<AdminUserDetail>(`/admin/users/${id}`),
  });
}

/**
 * The query key for one account's history.  It sits under `ADMIN_USERS_KEY`, so every
 * save and status action on the record, which invalidates that key, reads it again.
 */
export function adminUserHistoryKey(
  id: number | string,
): readonly [...typeof ADMIN_USERS_KEY, 'history', string] {
  return [...ADMIN_USERS_KEY, 'history', String(id)] as const;
}

/** One account's role and status changes, newest first, from `/admin/users/{id}/history`. */
export function useAdminUserHistory(id: string | number): UseQueryResult<AccountChange[]> {
  return useQuery({
    queryKey: adminUserHistoryKey(id),
    queryFn: () => api.get<AccountChange[]>(`/admin/users/${id}/history`),
  });
}

/**
 * Patches one account's roles.
 *
 * Also invalidates the signed-in caller's own `auth/me` query, since editing
 * your own roles changes what the nav may show.
 */
export function useUpdateAdminUser(
  id: string | number,
): UseMutationResult<AdminUserDetail, Error, AdminUserPatch> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: AdminUserPatch) => api.patch<AdminUserDetail>(`/admin/users/${id}`, patch),
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

/**
 * Mails the account a fresh verification link for its current address.
 *
 * Refetches the account on settling either way, since a refusal (the address was
 * verified since the page loaded) would otherwise leave the indicator beside it
 * showing stale, contradicting data.
 */
export function useSendEmailVerification(
  id: string | number,
): UseMutationResult<VerificationSentResult, Error, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.post<VerificationSentResult>(`/admin/users/${id}/send-email-verification`),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: adminUserKey(id) });
    },
  });
}

/**
 * Clears the bounce recorded against the account's address:
 * `POST /admin/users/{id}/clear-bounce`. The answer replaces the cached record, and the
 * list and the member records are read again, since both show the flag.
 */
export function useClearBounce(id: string | number): UseMutationResult<AdminUser, Error, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<AdminUser>(`/admin/users/${id}/clear-bounce`),
    onSuccess: (user) => {
      queryClient.setQueryData(adminUserKey(id), user);
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: ADMIN_USERS_KEY }),
        queryClient.invalidateQueries({ queryKey: MEMBERS_KEY }),
      ]);
    },
  });
}

/** The status actions on the user record, by the path segment each posts to. */
export type AccountStatusAction = 'deactivate' | 'reactivate' | 'block' | 'unblock';

/**
 * One of the user record's status actions: `POST /admin/users/{id}/{action}`.
 *
 * The answer is the record as it stands afterwards, which replaces the cached one; the
 * list, the member records, and the finance area are refreshed too, since deactivating
 * cancels renewals and suspends the membership.
 */
export function useAccountStatusAction(
  id: string | number,
): UseMutationResult<AdminUserDetail, Error, AccountStatusAction> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (action: AccountStatusAction) =>
      api.post<AdminUserDetail>(`/admin/users/${id}/${action}`),
    onSuccess: (user) => {
      queryClient.setQueryData(adminUserKey(id), user);
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: ADMIN_USERS_KEY }),
        queryClient.invalidateQueries({ queryKey: MEMBERS_KEY }),
        queryClient.invalidateQueries({ queryKey: FINANCE_KEY }),
      ]);
    },
  });
}
