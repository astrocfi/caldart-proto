/** Queries behind `/portal/bulk-email/mail-delivery`: the mail delivery (DNS) check. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type { MailDeliveryCheck } from '@/portal/api/types';

export const MAIL_DELIVERY_KEY = ['mail', 'delivery-check'] as const;

/** The mail delivery report, via `GET /mail/delivery-check` (the server caches it five minutes). */
export function useMailDeliveryCheck(): UseQueryResult<MailDeliveryCheck> {
  return useQuery({
    queryKey: MAIL_DELIVERY_KEY,
    queryFn: () => api.get<MailDeliveryCheck>('/mail/delivery-check'),
  });
}

/** Look every record up again with `?refresh=true` and replace the cached report with the answer. */
export function useRecheckMailDelivery(): UseMutationResult<MailDeliveryCheck, unknown, void> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.get<MailDeliveryCheck>('/mail/delivery-check', { query: { refresh: true } }),
    onSuccess: (report) => {
      queryClient.setQueryData(MAIL_DELIVERY_KEY, report);
    },
  });
}
