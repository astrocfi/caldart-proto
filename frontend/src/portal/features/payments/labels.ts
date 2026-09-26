/** The words the member's money screens use for a standing authority. */
import type { MandateCadence, MandateKind } from '@/portal/api/types';

/** What each kind of authority is called, as the emails name it too. */
const MANDATE_KIND_LABELS: Record<MandateKind, string> = {
  renewal: 'Automatic renewal',
  both: 'Automatic renewal and contribution',
  contribution: 'Recurring donation',
};

/** How often each cadence charges, as a choice: `Monthly` and so on. */
export const CADENCE_LABELS: Record<MandateCadence, string> = {
  monthly: 'Monthly',
  quarterly: 'Quarterly',
  yearly: 'Yearly',
};

/** How often each cadence charges, in running prose: `each month` and so on. */
export const CADENCE_PHRASES: Record<MandateCadence, string> = {
  monthly: 'each month',
  quarterly: 'each quarter',
  yearly: 'each year',
};

/** The cadences in the order a chooser offers them. */
export const CADENCE_ORDER: MandateCadence[] = ['monthly', 'quarterly', 'yearly'];

/**
 * The authority named as a thing: `Recurring donation`, `Automatic renewal`, and
 * `Automatic renewal and contribution`.
 *
 * It is what a sentence about the whole authority starts with, so the wording
 * follows the mandate rather than the screen.
 */
export function automaticKindLabel(kind: MandateKind): string {
  return MANDATE_KIND_LABELS[kind];
}

/**
 * The heading of the card that states the authority the dashboard reads.
 *
 * A life member has nothing to renew, so the authority that matters to them is
 * their recurring donation; everybody else's is their automatic renewal.
 */
export function automaticCardTitle(isLifetime: boolean): string {
  return isLifetime ? 'Recurring donation' : 'Automatic renewal';
}

/**
 * The Payments page's lede: what the screen covers, in reading order.
 *
 * Somebody with no membership to renew -- a life member or a friend -- is not
 * told about a renewal they will not get.
 */
export function paymentsPageLede(renews: boolean): string {
  const renewal = renews ? ' whether CalDART renews your membership for you,' : '';
  return `Your recurring donation,${renewal} your receipts, and your contribution statements.`;
}
