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
  GrantTermPayload,
  MemberCreatePayload,
  MemberDetail,
  MemberRow,
  MemberTerm,
  MemberUpdatePayload,
  Paginated,
  TermUpdatePayload,
} from '@/portal/api/types';
import { FINANCE_KEY } from '@/portal/features/admin-payments/api';
import type { FilterValues } from '@/portal/reports/types';

export const MEMBERS_KEY = ['admin-members'] as const;

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

/** One member's detail record, or disabled while `id` is null or not a number. */
export function useMember(id: number | null): UseQueryResult<MemberDetail> {
  return useQuery({
    queryKey: [...MEMBERS_KEY, 'detail', id],
    queryFn: () => api.get<MemberDetail>(`/admin/members/${id}`),
    enabled: id !== null && Number.isFinite(id),
  });
}

function useInvalidateMembers(): () => Promise<void> {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: MEMBERS_KEY });
}

/**
 * Invalidates every member query, the users list, and the finance area, for a change
 * that reaches an account's money as well as its record.
 */
function useInvalidateAccounts(): () => Promise<void> {
  const queryClient = useQueryClient();
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: MEMBERS_KEY }),
      queryClient.invalidateQueries({ queryKey: FINANCE_KEY }),
      queryClient.invalidateQueries({ queryKey: ADMIN_USERS_KEY }),
    ]);
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
 * account, so the finance area and the users list are invalidated with the members.
 */
export function useDeleteMember(id: number): UseMutationResult<null, Error, void> {
  const invalidate = useInvalidateAccounts();
  return useMutation({
    mutationFn: () => api.delete<null>(`/admin/members/${id}`),
    onSuccess: () => invalidate(),
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
 * One of the danger zone's account actions: `POST /admin/members/{id}/{action}`.
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
