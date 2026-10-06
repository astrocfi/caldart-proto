/**
 * The client for what CalDART management keeps to use again: saved templates
 * (`/bulk-email/templates`), saved recipient groups (`/bulk-email/groups`), and
 * **Duplicate** (`POST /bulk-email/{id}/duplicate`).
 *
 * A template fills a draft (`.../apply-template`) and a group adds its people to a
 * batch (`.../batch/add-group`); either change reads the email and its batch again.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient, UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type {
  BulkEmailAddResult,
  BulkEmailDetail,
  EmailTemplate,
  EmailTemplatePatch,
  EmailTemplateWrite,
  GroupPeople,
  GroupPerson,
  PersonMatch,
  RecipientGroup,
  RecipientGroupFilter,
  RecipientGroupWrite,
  SaveGroupRequest,
} from '@/portal/api/types';
import { API_BASE } from '@/portal/urlPrefix';
import { BULK_EMAIL_KEY, batchKey, emailKey } from './api';

const TEMPLATES_KEY = [...BULK_EMAIL_KEY, 'templates'] as const;
const GROUPS_KEY = [...BULK_EMAIL_KEY, 'groups'] as const;

/** The cache key of one group's people now. */
function peopleKey(id: number): readonly unknown[] {
  return [...GROUPS_KEY, 'people', id];
}

/* ------------------------------------------------------------------ templates */

/** Every saved template, by name. */
export function useTemplates(): UseQueryResult<EmailTemplate[]> {
  return useQuery({
    queryKey: TEMPLATES_KEY,
    queryFn: () => api.get<EmailTemplate[]>('/bulk-email/templates'),
  });
}

/** Saves a template; a refusal is an `ApiError` keyed by field (`name`, `subject`, ...). */
export function useCreateTemplate(): UseMutationResult<EmailTemplate, Error, EmailTemplateWrite> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: EmailTemplateWrite) =>
      api.post<EmailTemplate>('/bulk-email/templates', input),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: TEMPLATES_KEY }),
  });
}

export interface TemplateEdit {
  id: number;
  patch: EmailTemplatePatch;
}

/** Renames or edits a template, with the same refusals as saving one. */
export function useUpdateTemplate(): UseMutationResult<EmailTemplate, Error, TemplateEdit> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: TemplateEdit) =>
      api.patch<EmailTemplate>(`/bulk-email/templates/${id}`, patch),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: TEMPLATES_KEY }),
  });
}

/** Deletes a template. */
export function useDeleteTemplate(): UseMutationResult<void, Error, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/bulk-email/templates/${id}`),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: TEMPLATES_KEY }),
  });
}

/**
 * Fills email `id` from a template, via `POST .../apply-template`; the email as saved
 * goes into the cache before the caller hears of it.
 */
export function useApplyTemplate(id: number): UseMutationResult<BulkEmailDetail, Error, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (template: number) =>
      api.post<BulkEmailDetail>(`/bulk-email/${id}/apply-template`, { template }),
    onSuccess: (filled) => {
      queryClient.setQueryData(emailKey(id), filled);
      void queryClient.invalidateQueries({ queryKey: batchKey(id) });
    },
  });
}

/* ---------------------------------------------------------------- duplicate */

/** Copies email `id` into a fresh draft of the caller's own; resolves to the draft. */
export function useDuplicate(
  id: number,
): UseMutationResult<BulkEmailDetail, Error, { copyRecipients: boolean }> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ copyRecipients }: { copyRecipients: boolean }) =>
      api.post<BulkEmailDetail>(`/bulk-email/${id}/duplicate`, {
        copy_recipients: copyRecipients,
      }),
    onSuccess: (copy) => {
      queryClient.setQueryData(emailKey(copy.id), copy);
      void queryClient.invalidateQueries({ queryKey: [...BULK_EMAIL_KEY, 'drafts'] });
    },
  });
}

/* ------------------------------------------------------------------- groups */

/** Every saved recipient group, by name, with how many people each holds now. */
export function useGroups(): UseQueryResult<RecipientGroup[]> {
  return useQuery({
    queryKey: GROUPS_KEY,
    queryFn: () => api.get<RecipientGroup[]>('/bulk-email/groups'),
  });
}

/** One group, its filter sets included. */
export function useGroup(id: number): UseQueryResult<RecipientGroup> {
  return useQuery({
    queryKey: [...GROUPS_KEY, 'one', id],
    queryFn: () => api.get<RecipientGroup>(`/bulk-email/groups/${id}`),
  });
}

/** Everybody in group `id` now. */
export function useGroupPeople(id: number): UseQueryResult<GroupPeople> {
  return useQuery({
    queryKey: peopleKey(id),
    queryFn: () => api.get<GroupPeople>(`/bulk-email/groups/${id}/members`),
  });
}

/** Makes an empty group; a taken name is an `ApiError` keyed `name`. */
export function useCreateGroup(): UseMutationResult<RecipientGroup, Error, RecipientGroupWrite> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: RecipientGroupWrite) =>
      api.post<RecipientGroup>('/bulk-email/groups', input),
    onSuccess: () => invalidateGroups(queryClient),
  });
}

/** Renames group `id`; a taken name is an `ApiError` keyed `name`. */
export function useRenameGroup(id: number): UseMutationResult<RecipientGroup, Error, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.patch<RecipientGroup>(`/bulk-email/groups/${id}`, { name }),
    onSuccess: () => invalidateGroups(queryClient),
  });
}

/** Deletes a group; the batches it was added to keep their people. */
export function useDeleteGroup(): UseMutationResult<void, Error, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/bulk-email/groups/${id}`),
    onSuccess: () => invalidateGroups(queryClient),
  });
}

/** Adds one account to the fixed group `id`. */
export function useAddGroupMember(id: number): UseMutationResult<GroupPerson, Error, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (user: number) =>
      api.post<GroupPerson>(`/bulk-email/groups/${id}/members`, { user }),
    onSuccess: () => invalidateGroups(queryClient),
  });
}

/** Takes one account out of the fixed group `id`. */
export function useRemoveGroupMember(id: number): UseMutationResult<void, Error, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (user: number) => api.delete<void>(`/bulk-email/groups/${id}/members/${user}`),
    onSuccess: () => invalidateGroups(queryClient),
  });
}

/** Adds one filter set to the live group `id`, its blank filters dropped. */
export function useAddGroupFilters(
  id: number,
): UseMutationResult<RecipientGroupFilter, Error, Record<string, string>> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (filters: Record<string, string>) =>
      api.post<RecipientGroupFilter>(`/bulk-email/groups/${id}/filters`, { filters }),
    onSuccess: () => invalidateGroups(queryClient),
  });
}

/** Takes one filter set out of the live group `id`. */
export function useRemoveGroupFilters(id: number): UseMutationResult<void, Error, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (filterSet: number) =>
      api.delete<void>(`/bulk-email/groups/${id}/filters/${filterSet}`),
    onSuccess: () => invalidateGroups(queryClient),
  });
}

/**
 * The members and friends whose name or address holds `term`, for the typeahead
 * that adds somebody to a fixed group; idle while `term` is empty.
 */
export function usePeopleMatching(term: string): UseQueryResult<PersonMatch[]> {
  return useQuery({
    queryKey: [...GROUPS_KEY, 'people-search', term],
    queryFn: () =>
      api.get<PersonMatch[]>(`/bulk-email/groups/people?search=${encodeURIComponent(term)}`),
    enabled: term !== '',
  });
}

/** Adds a saved group's people to email `id`'s batch, via `POST .../batch/add-group`. */
export function useAddGroupToBatch(
  id: number,
): UseMutationResult<BulkEmailAddResult, Error, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (group: number) =>
      api.post<BulkEmailAddResult>(`/bulk-email/${id}/batch/add-group`, { group }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: emailKey(id) });
      void queryClient.invalidateQueries({ queryKey: batchKey(id) });
      void queryClient.invalidateQueries({ queryKey: [...BULK_EMAIL_KEY, 'drafts'] });
    },
  });
}

/**
 * Saves the search on email `id`'s compose screen as a group, via `POST .../save-group`:
 * a live group keeps the filters, a fixed group the people they match.
 */
export function useSaveGroup(
  id: number,
): UseMutationResult<RecipientGroup, Error, SaveGroupRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: SaveGroupRequest) =>
      api.post<RecipientGroup>(`/bulk-email/${id}/save-group`, input),
    onSuccess: () => invalidateGroups(queryClient),
  });
}

/** The href of a group's people as a CSV, `GET /bulk-email/groups/{id}/members.csv`. */
export function groupCsvUrl(id: number): string {
  return `${API_BASE}/bulk-email/groups/${id}/members.csv`;
}

/** Read every group list, every group, and every group's people again. */
function invalidateGroups(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: GROUPS_KEY });
}
