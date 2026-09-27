/**
 * The shapes the notification endpoints under `/api/v1/notifications/` answer
 * with and accept.
 *
 * They belong in `@/portal/api/types`, where the contract test holds every API
 * shape to the server's schema; they are declared here until the server's
 * notification endpoints and their types land there.
 */
import type { IsoDateTime, RoleSlug } from '@/portal/api/types';

/** The headings the screen groups the events under, in the order it shows them. */
export type NotificationCategory = 'Membership' | 'Money' | 'Accounts' | 'Aircraft';

/**
 * One event an address can subscribe to, from `GET /notifications/events`.
 *
 * `roles` are the roles whose holders may receive it; a system administrator
 * may receive every event.
 */
export interface NotificationEvent {
  slug: string;
  label: string;
  category: NotificationCategory;
  description: string;
  roles: RoleSlug[];
}

/**
 * One address and the events it hears about, from `/notifications/subscriptions`.
 *
 * `recipient_user` is the account that holds the address, or null for an
 * address outside CalDART, whose `recipient_name` is then blank.  `events` are
 * slugs in catalog order.
 */
export interface NotificationSubscription {
  id: number;
  recipient_user: number | null;
  recipient_name: string;
  recipient_email: string;
  events: string[];
  is_active: boolean;
  created_by_name: string;
  created_at: IsoDateTime;
  updated_at: IsoDateTime;
}

/**
 * The body of `POST /notifications/subscriptions`.  `confirmed` must be true
 * when no account holds `recipient_email`.
 */
export interface NotificationSubscriptionCreate {
  recipient_email: string;
  events: string[];
  confirmed?: boolean;
}

/** The fields `PATCH /notifications/subscriptions/{id}` may change. */
export type NotificationSubscriptionPatch = Partial<
  Pick<NotificationSubscription, 'events' | 'is_active'>
>;
