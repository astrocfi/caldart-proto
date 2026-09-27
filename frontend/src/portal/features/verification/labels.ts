/**
 * What each verified item and each kind of photo ID is called on every screen.
 *
 * The photo ID vocabulary is the portal's shared one (`@/portal/choices`), so the
 * profile's select and a leader's status card read the same words.
 */
import type { VerificationItem } from '@/portal/api/types';

export { PHOTO_ID_LABELS, PHOTO_ID_TYPES } from '@/portal/choices';

/** A person's items, in the order the screens list them. */
export const ITEM_SLUGS: readonly VerificationItem[] = ['certificate', 'medical', 'photo_id'];

export const ITEM_LABELS: Record<VerificationItem, string> = {
  certificate: 'Pilot certificate',
  medical: 'Medical',
  photo_id: 'Photo ID',
};
