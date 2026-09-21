/**
 * Data access for the members-admin screens.
 *
 * Every list query is keyed on the filters, so changing a filter is a new
 * query rather than a refetch of the same one, and every mutation invalidates
 * the whole `admin-members` tree.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { API_BASE, api } from '../../api/client';
import type {
  GrantTermPayload,
  MemberCreatePayload,
  MemberDetail,
  MemberRow,
  MemberTerm,
  MemberUpdatePayload,
  Paginated,
  TermUpdatePayload,
} from '../../api/types';
import type { MemberFilters } from './types';
import { FILTER_KEYS } from './types';

export const MEMBERS_KEY = ['admin-members'] as const;

/** Drop empty values so the URL only carries filters that are set. */
export function filterParams(filters: Partial<MemberFilters>): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    const value = filters[key];
    if (value) params.set(key, value);
  }
  return params;
}

/** The href behind the Export CSV / Export PDF buttons, filters included. */
export function exportUrl(format: 'csv' | 'pdf', filters: Partial<MemberFilters>): string {
  const query = filterParams(filters).toString();
  const base = `${API_BASE}/admin/members/export.${format}`;
  return query ? `${base}?${query}` : base;
}

export interface MemberListQuery extends Partial<MemberFilters> {
  page?: number;
  page_size?: number;
}

export function useMembers(query: MemberListQuery) {
  const params = filterParams(query);
  if (query.page && query.page > 1) params.set('page', String(query.page));
  if (query.page_size) params.set('page_size', String(query.page_size));
  const search = params.toString();

  return useQuery({
    queryKey: [...MEMBERS_KEY, 'list', search],
    queryFn: () => api.get<Paginated<MemberRow>>(`/admin/members${search ? `?${search}` : ''}`),
  });
}

export function useMember(id: number | null) {
  return useQuery({
    queryKey: [...MEMBERS_KEY, 'detail', id],
    queryFn: () => api.get<MemberDetail>(`/admin/members/${id}`),
    enabled: id !== null && Number.isFinite(id),
  });
}

// The DART and plan catalogs belong to the profile feature;
// re-exported so the admin screens use exactly one query key for each.
export { useDarts, usePlans } from '../profile/api';

function useInvalidateMembers() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: MEMBERS_KEY });
}

export function useCreateMember() {
  const invalidate = useInvalidateMembers();
  return useMutation({
    mutationFn: (payload: MemberCreatePayload) => api.post<MemberDetail>('/admin/members', payload),
    onSuccess: () => invalidate(),
  });
}

export function useUpdateMember(id: number) {
  const invalidate = useInvalidateMembers();
  return useMutation({
    mutationFn: (payload: MemberUpdatePayload) =>
      api.patch<MemberDetail>(`/admin/members/${id}`, payload),
    onSuccess: () => invalidate(),
  });
}

export function useDeleteMember(id: number) {
  const invalidate = useInvalidateMembers();
  return useMutation({
    mutationFn: () => api.delete<null>(`/admin/members/${id}`),
    onSuccess: () => invalidate(),
  });
}

export function useGrantTerm(id: number) {
  const invalidate = useInvalidateMembers();
  return useMutation({
    mutationFn: (payload: GrantTermPayload) =>
      api.post<MemberTerm>(`/admin/members/${id}/memberships`, payload),
    onSuccess: () => invalidate(),
  });
}

export function useUpdateTerm() {
  const invalidate = useInvalidateMembers();
  return useMutation({
    mutationFn: ({ termId, ...payload }: TermUpdatePayload & { termId: number }) =>
      api.patch<MemberTerm>(`/admin/memberships/${termId}`, payload),
    onSuccess: () => invalidate(),
  });
}
