/**
 * The client for the bulk email endpoints under `/api/v1/bulk-email`.
 *
 * A preview (`POST /bulk-email/preview`) lists who a message would reach and
 * sends nothing; a send (`POST /bulk-email/send`) rebuilds that list, sends, and
 * answers with every person's result.  The history and each past send are read
 * from `GET /bulk-email` and `GET /bulk-email/{id}`, and both lists download as
 * CSV files.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type {
  BulkEmail,
  BulkEmailDetail,
  BulkEmailMessage,
  BulkEmailPreview,
} from '@/portal/api/types';
import type { FilterValues } from '@/portal/reports/types';
import { API_BASE } from '@/portal/urlPrefix';

export const BULK_EMAIL_KEY = ['bulk-email'] as const;

/** Every bulk email sent, the most recent first, via `GET /bulk-email`. */
export function useBulkEmails(): UseQueryResult<BulkEmail[]> {
  return useQuery({
    queryKey: BULK_EMAIL_KEY,
    queryFn: () => api.get<BulkEmail[]>('/bulk-email'),
  });
}

/**
 * One sent bulk email with every person's result, via `GET /bulk-email/{id}`.
 *
 * @param id the send to read, or null to read nothing yet.
 */
export function useBulkEmail(id: number | null): UseQueryResult<BulkEmailDetail> {
  return useQuery({
    queryKey: [...BULK_EMAIL_KEY, id],
    queryFn: () => api.get<BulkEmailDetail>(`/bulk-email/${String(id)}`),
    enabled: id !== null,
  });
}

/**
 * Lists who a message would reach, via `POST /bulk-email/preview`; nothing is sent.
 *
 * A refusal is an `ApiError` whose body is keyed by field: `subject`, `body`, or
 * `filters`.
 */
export function usePreviewBulkEmail(): UseMutationResult<
  BulkEmailPreview,
  unknown,
  BulkEmailMessage
> {
  return useMutation({
    mutationFn: (message: BulkEmailMessage) =>
      api.post<BulkEmailPreview>('/bulk-email/preview', message),
  });
}

/**
 * Sends a message to everybody its filters select, via `POST /bulk-email/send`.
 *
 * The history is read again once the send is stored.
 */
export function useSendBulkEmail(): UseMutationResult<BulkEmailDetail, unknown, BulkEmailMessage> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (message: BulkEmailMessage) =>
      api.post<BulkEmailDetail>('/bulk-email/send', message),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: BULK_EMAIL_KEY });
    },
  });
}

/**
 * The filters that carry a value, as a bulk email takes them.
 *
 * @param filters the filter bar's values, every key present.
 */
export function givenFilters(filters: FilterValues): Record<string, string> {
  return Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== ''));
}

/**
 * The href of the preview's list as a CSV, `GET /bulk-email/preview.csv`.
 *
 * @param filters the filter bar's values; blank ones are left out.
 */
export function previewCsvUrl(filters: FilterValues): string {
  const search = new URLSearchParams(givenFilters(filters)).toString();
  const base = `${API_BASE}/bulk-email/preview.csv`;
  return search === '' ? base : `${base}?${search}`;
}

/**
 * The href of one send's results as a CSV, `GET /bulk-email/{id}/recipients.csv`.
 *
 * @param id the send.
 */
export function recipientsCsvUrl(id: number): string {
  return `${API_BASE}/bulk-email/${id}/recipients.csv`;
}
