/**
 * The notifications screen's client for `/api/v1/notifications/`: the catalog
 * of events, and the subscriptions that say which address hears about which.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query';

import { api } from '@/portal/api/client';
import type {
  NotificationEvent,
  NotificationSubscription,
  NotificationSubscriptionCreate,
  NotificationSubscriptionPatch,
} from '@/portal/api/types';

export const NOTIFICATION_EVENTS_KEY = ['notifications', 'events'] as const;
export const NOTIFICATION_SUBSCRIPTIONS_KEY = ['notifications', 'subscriptions'] as const;

/**
 * Every event an address can subscribe to, in catalog order, via
 * `GET /notifications/events`.  The catalog never changes while the portal is
 * open, so it is fetched once and kept.
 */
export function useNotificationEvents(): UseQueryResult<NotificationEvent[]> {
  return useQuery({
    queryKey: NOTIFICATION_EVENTS_KEY,
    queryFn: () => api.get<NotificationEvent[]>('/notifications/events'),
    staleTime: Infinity,
  });
}

/** Every notification subscription, via `GET /notifications/subscriptions`. */
export function useNotificationSubscriptions(): UseQueryResult<NotificationSubscription[]> {
  return useQuery({
    queryKey: NOTIFICATION_SUBSCRIPTIONS_KEY,
    queryFn: () => api.get<NotificationSubscription[]>('/notifications/subscriptions'),
  });
}

/** Reads the subscriptions again once one of them has changed. */
function useInvalidateSubscriptions(): () => void {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: NOTIFICATION_SUBSCRIPTIONS_KEY });
  };
}

/**
 * Subscribes an address via `POST /notifications/subscriptions`.
 *
 * A refusal is an `ApiError` whose body is keyed by field: `recipient_email`
 * for an invalid or already subscribed address, `events` for none chosen or one
 * the account may not receive, and `confirmed` for an address no account holds.
 */
export function useCreateNotificationSubscription(): UseMutationResult<
  NotificationSubscription,
  unknown,
  NotificationSubscriptionCreate
> {
  const handleSuccess = useInvalidateSubscriptions();
  return useMutation({
    mutationFn: (body: NotificationSubscriptionCreate) =>
      api.post<NotificationSubscription>('/notifications/subscriptions', body),
    onSuccess: handleSuccess,
  });
}

/** One subscription and the fields to change on it. */
export interface NotificationSubscriptionEdit {
  id: number;
  patch: NotificationSubscriptionPatch;
}

/**
 * Changes a subscription's events or pauses and resumes it via
 * `PATCH /notifications/subscriptions/{id}`; a refusal is keyed `events`.
 */
export function useUpdateNotificationSubscription(): UseMutationResult<
  NotificationSubscription,
  unknown,
  NotificationSubscriptionEdit
> {
  const handleSuccess = useInvalidateSubscriptions();
  return useMutation({
    mutationFn: ({ id, patch }: NotificationSubscriptionEdit) =>
      api.patch<NotificationSubscription>(`/notifications/subscriptions/${id}`, patch),
    onSuccess: handleSuccess,
  });
}

/** Deletes a subscription via `DELETE /notifications/subscriptions/{id}`. */
export function useDeleteNotificationSubscription(): UseMutationResult<void, unknown, number> {
  const handleSuccess = useInvalidateSubscriptions();
  return useMutation({
    mutationFn: (id: number) => api.delete<void>(`/notifications/subscriptions/${id}`),
    onSuccess: handleSuccess,
  });
}
