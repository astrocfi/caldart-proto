/** The words the member's money screens use for a standing authority. */
import type { MandateKind } from '@/portal/api/types';

/** What each kind of authority charges for, as the emails name it too. */
const MANDATE_KIND_LABELS: Record<MandateKind, string> = {
  renewal: 'renewal',
  both: 'renewal and contribution',
  contribution: 'contribution',
};

/** `renewal`, `renewal and contribution`, or `contribution`. */
function mandateKindLabel(kind: MandateKind): string {
  return MANDATE_KIND_LABELS[kind];
}

/**
 * The authority named as a thing: `Automatic contribution`, and so on.
 *
 * It is what a sentence about the whole authority starts with, so the wording
 * follows the mandate rather than the screen: a life member's reads
 * `Automatic contribution` because nothing of theirs renews.
 */
export function automaticKindLabel(kind: MandateKind): string {
  return `Automatic ${mandateKindLabel(kind)}`;
}

/**
 * The heading over the card, and the words its toasts use.
 *
 * A life member has nothing to renew, so their card is about the contribution
 * whatever authority they hold, or hold none.
 */
export function automaticCardTitle(isLifetime: boolean): string {
  return isLifetime ? 'Automatic contribution' : 'Automatic renewal';
}
