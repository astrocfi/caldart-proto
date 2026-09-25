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
import type {
  GrantTermPayload,
  MemberCreatePayload,
  MemberDetail,
  MemberRow,
  MemberTerm,
  MemberUpdatePayload,
  Paginated,
  TermUpdatePayload,
} from '@/portal/api/types';
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

/** Deletes a member with no payment history; invalidates `admin-members` on success. */
export function useDeleteMember(id: number): UseMutationResult<null, Error, void> {
  const invalidate = useInvalidateMembers();
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
