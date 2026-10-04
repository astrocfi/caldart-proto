/**
 * The client for the Callouts screens, under `/api/v1/bulk-email/callouts`: every
 * mission callout, one callout's answers, **Remind non-responders**, and **Close
 * now**. A callout that still takes answers is read again every half minute, so the
 * answers arriving show without a reload.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type { CalloutDetail, CalloutSummary } from '@/portal/api/types';
import { BULK_EMAIL_KEY } from '@/portal/features/bulk-email/api';
import { API_BASE } from '@/portal/urlPrefix';

export const CALLOUTS_KEY = ['callouts'] as const;

/** How often an open callout is read again for the answers arriving. */
export const ANSWERS_POLL_MS = 30_000;

/** The cache key of one callout. */
export function calloutKey(id: number): readonly unknown[] {
  return [...CALLOUTS_KEY, id];
}

/** Every callout the signed-in sender may open, newest first. */
export function useCallouts(): UseQueryResult<CalloutSummary[]> {
  return useQuery({
    queryKey: CALLOUTS_KEY,
    queryFn: () => api.get<CalloutSummary[]>('/bulk-email/callouts'),
  });
}

/** One callout with every answer, read again while it takes answers. */
export function useCallout(id: number): UseQueryResult<CalloutDetail> {
  return useQuery({
    queryKey: calloutKey(id),
    queryFn: () => api.get<CalloutDetail>(`/bulk-email/callouts/${id}`),
    refetchInterval: (query) => (query.state.data?.is_open === true ? ANSWERS_POLL_MS : false),
  });
}

/** The actions of one callout: each a `POST /bulk-email/callouts/{id}/<action>`. */
export type CalloutAction = 'remind' | 'close';

/** **Remind non-responders** or **Close now** on callout `id`. */
export function useCalloutAction(
  id: number,
  action: CalloutAction,
): UseMutationResult<CalloutDetail, unknown, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<CalloutDetail>(`/bulk-email/callouts/${id}/${action}`),
    onSuccess: (saved) => {
      queryClient.setQueryData(calloutKey(id), saved);
      void queryClient.invalidateQueries({ queryKey: CALLOUTS_KEY, exact: true });
      // A reminder queues the email again, which the Sent screens show.
      void queryClient.invalidateQueries({ queryKey: BULK_EMAIL_KEY });
    },
  });
}

/** The href of one callout's answers as a CSV, `GET .../answers.csv`. */
export function answersCsvUrl(id: number): string {
  return `${API_BASE}/bulk-email/callouts/${id}/answers.csv`;
}
