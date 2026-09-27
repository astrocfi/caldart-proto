/** The words the notifications screen shows for a subscription and the event catalog. */
import type { NotificationEvent, NotificationSubscription } from '@/portal/api/types';

/** The headings the screen groups the events under, as the catalog names them. */
export type NotificationCategory = 'Membership' | 'Money' | 'Accounts' | 'Aircraft';

/** The categories, in the order the form groups the events under them. */
export const CATEGORIES: readonly NotificationCategory[] = [
  'Membership',
  'Money',
  'Accounts',
  'Aircraft',
];

/** One category's heading and its events, in catalog order. */
export interface EventGroup {
  category: NotificationCategory;
  events: NotificationEvent[];
}

/** The name of the account a subscription is bound to, or its bare address when none. */
export function recipientLabel(subscription: NotificationSubscription): string {
  return subscription.recipient_name === ''
    ? subscription.recipient_email
    : subscription.recipient_name;
}

/**
 * The labels of `slugs`, joined with commas in the order given.
 *
 * @param slugs the events a subscription lists.
 * @param events the catalog that names them; a slug it does not list reads as itself.
 * @returns `Sign-up, Donation received`, or `''` for no events.
 */
export function eventLabels(
  slugs: readonly string[],
  events: readonly NotificationEvent[],
): string {
  return slugs.map((slug) => events.find((event) => event.slug === slug)?.label ?? slug).join(', ');
}

/**
 * The catalog grouped under its categories, in `CATEGORIES` order, each keeping
 * the catalog's order and a category with no events left out.
 */
export function groupEvents(events: readonly NotificationEvent[]): EventGroup[] {
  return CATEGORIES.map((category) => ({
    category,
    events: events.filter((event) => event.category === category),
  })).filter((group) => group.events.length > 0);
}
