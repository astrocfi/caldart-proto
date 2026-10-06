/**
 * The client for a sent bulk email's delivery report: **Retry failed**
 * (`POST /bulk-email/{id}/retry`), one person's copy as it went
 * (`GET /bulk-email/{id}/recipients/{rid}/copy`), and hiding the email from the
 * recipients' Email to me page (`POST /bulk-email/{id}/hide`).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type { BulkEmailCopy, BulkEmailDetail, BulkEmailHideRequest } from '@/portal/api/types';
import { BULK_EMAIL_KEY, emailKey } from './api';

/** The cache key of one person's copy of one email. */
function copyKey(id: number, rowId: number): readonly unknown[] {
  return [...BULK_EMAIL_KEY, 'copy', id, rowId];
}

/**
 * One person's copy of email `id` as it went, read once the row is chosen.
 *
 * @param id the email.
 * @param rowId the person's row in the batch, or null while none is chosen.
 */
export function useRecipientCopy(id: number, rowId: number | null): UseQueryResult<BulkEmailCopy> {
  return useQuery({
    queryKey: copyKey(id, rowId ?? 0),
    queryFn: () => api.get<BulkEmailCopy>(`/bulk-email/${id}/recipients/${rowId}/copy`),
    enabled: rowId !== null,
  });
}

/** **Retry failed**: queues email `id`'s failed copies to go again now. */
export function useRetryFailed(id: number): UseMutationResult<BulkEmailDetail, unknown, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<BulkEmailDetail>(`/bulk-email/${id}/retry`),
    onSuccess: (queued) => {
      queryClient.setQueryData(emailKey(id), queued);
      // The batch, the lists, and every copy read before have all moved on.
      void queryClient.invalidateQueries({ queryKey: BULK_EMAIL_KEY });
    },
  });
}

/** Hides email `id` from the recipients' Email to me page, or shows it there again. */
export function useHideFromMessages(
  id: number,
): UseMutationResult<BulkEmailDetail, unknown, boolean> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (hidden: boolean) => {
      const body: BulkEmailHideRequest = { hidden };
      return api.post<BulkEmailDetail>(`/bulk-email/${id}/hide`, body);
    },
    onSuccess: (saved) => queryClient.setQueryData(emailKey(id), saved),
  });
}
