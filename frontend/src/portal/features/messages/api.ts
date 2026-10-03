/**
 * The client for the signed-in person's Messages: the bulk emails they received,
 * from `GET /messages`, and one of them as their own copy, from `GET /messages/{id}`.
 */
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type { BulkEmailMessage, BulkEmailMessageDetail } from '@/portal/api/types';

const MESSAGES_KEY = ['messages'] as const;

/** Every bulk email the signed-in person received, the most recently sent first. */
export function useMessages(): UseQueryResult<BulkEmailMessage[]> {
  return useQuery({
    queryKey: MESSAGES_KEY,
    queryFn: () => api.get<BulkEmailMessage[]>('/messages'),
  });
}

/** One bulk email the signed-in person received, as their own copy. */
export function useMessage(id: number): UseQueryResult<BulkEmailMessageDetail> {
  return useQuery({
    queryKey: [...MESSAGES_KEY, id],
    queryFn: () => api.get<BulkEmailMessageDetail>(`/messages/${id}`),
  });
}
