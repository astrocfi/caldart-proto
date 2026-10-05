/**
 * Data access for the members-admin screens.
 *
 * Every list query is keyed on the filters, so changing a filter is a new
 * query rather than a refetch of the same one, and every mutation invalidates
 * the whole `admin-members` tree.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import { ADMIN_USERS_KEY } from '@/portal/api/queries';
import type {
  BecomeFriendPayload,
  Dart,
  GrantTermPayload,
  MemberCreatePayload,
  MemberDetail,
  MemberRow,
  MemberTerm,
  MemberUpdatePayload,
  Paginated,
  Profile,
  TermUpdatePayload,
} from '@/portal/api/types';
import { FINANCE_KEY } from '@/portal/features/admin-payments/api';
import { PROFILE_KEY } from '@/portal/features/profile/api';
import type { FilterValues } from '@/portal/reports/types';

export const MEMBERS_KEY = ['admin-members'] as const;

/**
 * The DART on the signed-in reader's own profile, read only when `enabled`: a DART
 * leader's roster is the member list filtered to it.  Null while it loads, and for a
 * profile that names no DART.
 */
export function useOwnDart(enabled: boolean): Pick<Dart, 'id' | 'name'> | null {
  const profile = useQuery({
    queryKey: PROFILE_KEY,
    queryFn: () => api.get<Profile>('/me/profile'),
    enabled,
  });
  return profile.data?.dart ?? null;
}

export interface MemberListQuery {
  /** The members report's filters and `ordering`, by query parameter; an empty value is unset. */
  filters: FilterValues;
  page?: number;
  page_size?: number;
}

/**
 * The paginated member list for `/admin/members`, filtered and sorted by `query`.
 *
 * A change of page or filter is a different query, so the page already on screen
 * stands in for the one being fetched: the table holds still instead of collapsing
 * to a spinner and back.  `isPlaceholderData` says which of the two is showing.
 */
export function useMembers(query: MemberListQuery): UseQueryResult<Paginated<MemberRow>> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query.filters)) {
    if (value !== '') params.set(key, value);
  }
  if (query.page && query.page > 1) params.set('page', String(query.page));
  if (query.page_size) params.set('page_size', String(query.page_size));
  const search = params.toString();

  return useQuery({
    queryKey: [...MEMBERS_KEY, 'list', search],
    queryFn: () => api.get<Paginated<MemberRow>>(`/admin/members${search ? `?${search}` : ''}`),
    placeholderData: keepPreviousData,
  });
}

/** The query key of the member record `id`. */
function memberKey(id: number | null) {
  return [...MEMBERS_KEY, 'detail', id] as const;
}

/** One member's detail record, or disabled while `id` is null or not a number. */
export function useMember(id: number | null): UseQueryResult<MemberDetail> {
  return useQuery({
    queryKey: memberKey(id),
    queryFn: () => api.get<MemberDetail>(`/admin/members/${id}`),
    enabled: id !== null && Number.isFinite(id),
  });
}

function useInvalidateMembers(): () => Promise<void> {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: MEMBERS_KEY });
}

/** The finance reports and the renewals lists, keyed apart from the finance area. */
const PAYMENT_REPORTS_KEY = ['admin', 'payments'] as const;
const RENEWALS_KEY = ['admin', 'renewals'] as const;

/**
 * Invalidates every member query, the users list, the finance area, its reports, and
 * the renewals lists, for a change that reaches an account's money as well as its
 * record.
 */
function useInvalidateAccounts(): () => Promise<void> {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all(
      [MEMBERS_KEY, FINANCE_KEY, ADMIN_USERS_KEY, PAYMENT_REPORTS_KEY, RENEWALS_KEY].map(
        (queryKey) => queryClient.invalidateQueries({ queryKey }),
      ),
    );
  };
}

/** Creates a member account and profile; invalidates `admin-members` on success. */
export function useCreateMember(): UseMutationResult<MemberDetail, Error, MemberCreatePayload> {
  const invalidate = useInvalidateMembers();
  return useMutation({
    mutationFn: (payload: MemberCreatePayload) => api.post<MemberDetail>('/admin/members', payload),
    onSuccess: () => invalidate(),
  });
}

/** Patches a member's account and profile; invalidates `admin-members` on success. */
export function useUpdateMember(
  id: number,
): UseMutationResult<MemberDetail, Error, MemberUpdatePayload> {
  const invalidate = useInvalidateMembers();
  return useMutation({
    mutationFn: (payload: MemberUpdatePayload) =>
      api.patch<MemberDetail>(`/admin/members/${id}`, payload),
    onSuccess: () => invalidate(),
  });
}

/**
 * Deletes a member, friend, or donor. Their payments move to the "Deleted member {id}"
 * account, so the finance area, its reports, the renewals, and the users list are
 * invalidated with the members, and the deleted record's own query is dropped.
 */
export function useDeleteMember(id: number): UseMutationResult<null, Error, void> {
  const queryClient = useQueryClient();
  const invalidate = useInvalidateAccounts();
  return useMutation({
    mutationFn: () => api.delete<null>(`/admin/members/${id}`),
    // The record is gone: dropping its query, rather than refetching it, keeps the
    // record from flashing "could not be loaded" before the page moves on.
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: memberKey(id), exact: true });
      return invalidate();
    },
  });
}

/** Grants a membership term for a member; invalidates `admin-members` on success. */
export function useGrantTerm(id: number): UseMutationResult<MemberTerm, Error, GrantTermPayload> {
  const invalidate = useInvalidateMembers();
  return useMutation({
    mutationFn: (payload: GrantTermPayload) =>
      api.post<MemberTerm>(`/admin/members/${id}/memberships`, payload),
    onSuccess: () => invalidate(),
  });
}

/** Patches one membership term; invalidates `admin-members` on success. */
export function useUpdateTerm(): UseMutationResult<
  MemberTerm,
  Error,
  TermUpdatePayload & { termId: number }
> {
  const invalidate = useInvalidateMembers();
  return useMutation({
    mutationFn: ({ termId, ...payload }: TermUpdatePayload & { termId: number }) =>
      api.patch<MemberTerm>(`/admin/memberships/${termId}`, payload),
    onSuccess: () => invalidate(),
  });
}

/**
 * One of the Delete or deactivate tab's account actions: `POST /admin/members/{id}/{action}`.
 *
 * The answer is the member record as it stands afterwards. Every member query is
 * invalidated, and so are the users list and the finance area, since deactivating or making a friend
 * cancels the automatic renewal and may start a recurring donation.
 */
function useMemberAction<Body>(
  id: number,
  action: 'friend' | 'deactivate' | 'reactivate',
): UseMutationResult<MemberDetail, Error, Body> {
  const invalidate = useInvalidateAccounts();
  return useMutation({
    mutationFn: (body: Body) => api.post<MemberDetail>(`/admin/members/${id}/${action}`, body),
    onSuccess: () => invalidate(),
  });
}

/** Makes the member a friend, as their own switch would; may carry `keep_contribution`. */
export function useMakeFriend(
  id: number,
): UseMutationResult<MemberDetail, Error, BecomeFriendPayload> {
  return useMemberAction<BecomeFriendPayload>(id, 'friend');
}

/** Deactivates the member's account, as their own deactivation would. */
export function useDeactivateMember(id: number): UseMutationResult<MemberDetail, Error, void> {
  return useMemberAction<void>(id, 'deactivate');
}

/** Reactivates the member's account, as their own reactivation would. */
export function useReactivateMember(id: number): UseMutationResult<MemberDetail, Error, void> {
  return useMemberAction<void>(id, 'reactivate');
}
