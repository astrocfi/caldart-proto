/**
 * The client for the bulk email endpoints under `/api/v1/bulk-email`.
 *
 * A bulk email is a draft on the server from the moment Compose opens it: the
 * screen saves its subject and message as they are typed (`PATCH`), shows who the
 * member list's filters match (`.../batch/matches`), builds its batch with them
 * (`.../batch/add`), and queues it with
 * Send (`.../send`). The background sender does the sending; the screens poll
 * `GET /bulk-email/{id}` while an email waits to start or is sending.
 */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient, UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type {
  BulkEmailAddResult,
  BulkEmailBatch,
  BulkEmailDetail,
  BulkEmailMatch,
  BulkEmailPatch,
  BulkEmailSender,
  BulkEmailSendRequest,
  BulkEmailStatus,
  BulkEmailSummary,
  Paginated,
  SendableEmailType,
} from '@/portal/api/types';
import type { FilterValues } from '@/portal/reports/types';
import { API_BASE } from '@/portal/urlPrefix';

export const BULK_EMAIL_KEY = ['bulk-email'] as const;

/** How often a screen reads an email again while it waits to start or is sending. */
export const POLL_MS = 3000;

/** The statuses in which an email is still moving and worth reading again. */
const MOVING: readonly BulkEmailStatus[] = ['queued', 'sending'];

/** True while `status` is one the background sender has yet to finish. */
export function isMoving(status: BulkEmailStatus): boolean {
  return MOVING.includes(status);
}

/** The cache key of one email. */
export function emailKey(id: number): readonly unknown[] {
  return [...BULK_EMAIL_KEY, 'email', id];
}

/** The cache key of one email's batch. */
export function batchKey(id: number): readonly unknown[] {
  return [...BULK_EMAIL_KEY, 'batch', id];
}

const DRAFTS_KEY = [...BULK_EMAIL_KEY, 'drafts'] as const;
const SENT_KEY = [...BULK_EMAIL_KEY, 'sent'] as const;

/**
 * The cache key of the types the signed-in sender may send. It sits under the Email
 * types screen's key, so a change made there reaches the compose screen too.
 */
const SENDABLE_TYPES_KEY = ['email-types', 'sendable'] as const;

/** The types the signed-in sender may send, via `GET /email-types/sendable`. */
export function useSendableEmailTypes(): UseQueryResult<SendableEmailType[]> {
  return useQuery({
    queryKey: SENDABLE_TYPES_KEY,
    queryFn: () => api.get<SendableEmailType[]>('/email-types/sendable'),
  });
}

/** The cache key of who the signed-in sender may send to. */
const SENDER_KEY = [...BULK_EMAIL_KEY, 'sender'] as const;

/**
 * Who the signed-in sender may send to, via `GET /bulk-email/sender`: everyone for
 * CalDART management, the DART on their profile for a DART leader.  `enabled` false
 * asks nothing, for a screen shown to people who may not send bulk email at all.
 */
export function useBulkSender(enabled = true): UseQueryResult<BulkEmailSender> {
  return useQuery({
    queryKey: SENDER_KEY,
    queryFn: () => api.get<BulkEmailSender>('/bulk-email/sender'),
    enabled,
  });
}

/** Every draft and queued email, the most recently edited first. */
export function useDrafts(): UseQueryResult<BulkEmailSummary[]> {
  return useQuery({
    queryKey: DRAFTS_KEY,
    queryFn: () => api.get<BulkEmailSummary[]>('/bulk-email/drafts'),
    refetchInterval: (query) =>
      (query.state.data ?? []).some((row) => isMoving(row.status)) ? POLL_MS : false,
  });
}

/** Every email sending, sent, or stopped, newest first; read again while one is sending. */
export function useSentEmails(): UseQueryResult<BulkEmailSummary[]> {
  return useQuery({
    queryKey: SENT_KEY,
    queryFn: () => api.get<BulkEmailSummary[]>('/bulk-email/sent'),
    refetchInterval: (query) =>
      (query.state.data ?? []).some((row) => isMoving(row.status)) ? POLL_MS : false,
  });
}

/**
 * One email, via `GET /bulk-email/{id}`, read again every few seconds while it
 * waits to start or is sending.
 */
export function useBulkEmail(id: number): UseQueryResult<BulkEmailDetail> {
  return useQuery({
    queryKey: emailKey(id),
    queryFn: () => api.get<BulkEmailDetail>(`/bulk-email/${id}`),
    refetchInterval: (query) =>
      query.state.data !== undefined && isMoving(query.state.data.status) ? POLL_MS : false,
  });
}

/**
 * One email's batch, via `GET /bulk-email/{id}/batch`.
 *
 * @param id the email.
 * @param isPolling read it again every few seconds, while the email is sending.
 */
export function useBatch(id: number, isPolling = false): UseQueryResult<BulkEmailBatch> {
  return useQuery({
    queryKey: batchKey(id),
    queryFn: () => api.get<BulkEmailBatch>(`/bulk-email/${id}/batch`),
    refetchInterval: isPolling ? POLL_MS : false,
  });
}

/** Opens the caller's empty draft, or a fresh one, via `POST /bulk-email/drafts`. */
export function useOpenDraft(): UseMutationResult<BulkEmailDetail, unknown, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<BulkEmailDetail>('/bulk-email/drafts'),
    onSuccess: (draft) => {
      queryClient.setQueryData(emailKey(draft.id), draft);
      void queryClient.invalidateQueries({ queryKey: DRAFTS_KEY });
    },
  });
}

/** Saves the given fields of one email, via `PATCH /bulk-email/{id}`. */
export function useUpdateBulkEmail(
  id: number,
): UseMutationResult<BulkEmailDetail, unknown, BulkEmailPatch> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: BulkEmailPatch) => api.patch<BulkEmailDetail>(`/bulk-email/${id}`, patch),
    onSuccess: (saved) => {
      queryClient.setQueryData(emailKey(id), saved);
      void queryClient.invalidateQueries({ queryKey: DRAFTS_KEY });
    },
  });
}

/** Deletes a draft and its batch, via `DELETE /bulk-email/{id}`. */
export function useDeleteDraft(): UseMutationResult<void, unknown, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/bulk-email/${id}`),
    onSuccess: () => invalidateLists(queryClient),
  });
}

/** How many matched people one page of a search shows. */
export const MATCHES_PAGE_SIZE = 10;

/**
 * One page of the people the filters match for email `id`, before anybody is added,
 * via `GET /bulk-email/{id}/batch/matches`. The page shown stays while the next loads.
 *
 * @param id the email.
 * @param filters the filter bar's values; blank ones are left out.
 * @param page the page wanted, from 1.
 * @param enabled false while nobody can be added, when there is nothing to search.
 */
export function useBatchMatches(
  id: number,
  filters: FilterValues,
  page: number,
  enabled: boolean,
): UseQueryResult<Paginated<BulkEmailMatch>> {
  const given = givenFilters(filters);
  return useQuery({
    queryKey: [...BULK_EMAIL_KEY, 'matches', id, given, page],
    queryFn: () => {
      const params = new URLSearchParams({
        ...given,
        page: String(page),
        page_size: String(MATCHES_PAGE_SIZE),
      });
      return api.get<Paginated<BulkEmailMatch>>(`/bulk-email/${id}/batch/matches?${params}`);
    },
    placeholderData: keepPreviousData,
    enabled,
  });
}

/** Adds everybody the filters choose to the batch, via `POST .../batch/add`. */
export function useAddToBatch(
  id: number,
): UseMutationResult<BulkEmailAddResult, unknown, FilterValues> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (filters: FilterValues) =>
      api.post<BulkEmailAddResult>(`/bulk-email/${id}/batch/add`, {
        filters: givenFilters(filters),
      }),
    onSuccess: () => invalidateEmail(queryClient, id),
  });
}

/** Takes one person out of the batch, via `DELETE .../batch/{rid}`. */
export function useRemoveFromBatch(id: number): UseMutationResult<void, unknown, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rowId: number) => api.delete<void>(`/bulk-email/${id}/batch/${rowId}`),
    onSuccess: () => invalidateEmail(queryClient, id),
  });
}

/** Empties the batch, via `DELETE .../batch`. */
export function useClearBatch(id: number): UseMutationResult<BulkEmailBatch, unknown, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<BulkEmailBatch>(`/bulk-email/${id}/batch`),
    onSuccess: () => invalidateEmail(queryClient, id),
  });
}

/** The actions that move an email along: each a `POST /bulk-email/{id}/<action>`. */
export type BulkEmailAction = 'cancel' | 'stop' | 'resume';

/** Queues an email (Send or Schedule), via `POST /bulk-email/{id}/send`. */
export function useSendBulkEmail(
  id: number,
): UseMutationResult<BulkEmailDetail, unknown, BulkEmailSendRequest> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: BulkEmailSendRequest) =>
      api.post<BulkEmailDetail>(`/bulk-email/${id}/send`, request),
    onSuccess: (queued) => {
      queryClient.setQueryData(emailKey(id), queued);
      invalidateLists(queryClient);
    },
  });
}

/**
 * Cancels a queued email, stops a send, or sends the rest of a stopped one, via
 * `POST /bulk-email/{id}/<action>`.
 */
export function useBulkEmailAction(
  action: BulkEmailAction,
): UseMutationResult<BulkEmailDetail, unknown, number> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.post<BulkEmailDetail>(`/bulk-email/${id}/${action}`),
    onSuccess: (moved) => {
      queryClient.setQueryData(emailKey(moved.id), moved);
      invalidateEmail(queryClient, moved.id);
    },
  });
}

/**
 * The filters that carry a value, as an add takes them.
 *
 * @param filters the filter bar's values, every key present.
 */
export function givenFilters(filters: FilterValues): Record<string, string> {
  return Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== ''));
}

/** The href of one email's batch as a CSV, `GET /bulk-email/{id}/batch.csv`. */
export function batchCsvUrl(id: number): string {
  return `${API_BASE}/bulk-email/${id}/batch.csv`;
}

/** The href of one send's results as a CSV, `GET /bulk-email/{id}/recipients.csv`. */
export function recipientsCsvUrl(id: number): string {
  return `${API_BASE}/bulk-email/${id}/recipients.csv`;
}

/** Read the two lists again, after an email moved between them or went away. */
function invalidateLists(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: DRAFTS_KEY });
  void queryClient.invalidateQueries({ queryKey: SENT_KEY });
}

/** Read one email, its batch, and the lists again after a change to it. */
function invalidateEmail(queryClient: QueryClient, id: number): void {
  void queryClient.invalidateQueries({ queryKey: emailKey(id) });
  void queryClient.invalidateQueries({ queryKey: batchKey(id) });
  invalidateLists(queryClient);
}
