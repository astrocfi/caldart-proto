/**
 * Wording for the coded fields on a leader's status card.
 *
 * The vocabulary itself is the portal's shared one (`@/portal/choices`), so a
 * certificate reads the same on the ramp as it does in the member's own
 * profile form; this module re-exports what the card needs and adds the one
 * phrasing only the leader screens use: a medical said in a single breath.
 */
import type { LeaderMedical, MedicalType } from '@/portal/api/types';
import { formatDate } from '@/portal/components/DateText';

export {
  CERTIFICATE_LABELS,
  IFR_LABELS,
  MEDICAL_LABELS,
  RATING_LABELS,
  ratingLabels,
} from '@/portal/choices';

/**
 * A medical named the way a leader says it out loud.
 *
 * The profile form asks for a class, so it offers "Third class"; the ramp asks
 * which medical the pilot holds, which is "Class 3".
 */
export const MEDICAL_PHRASES: Record<MedicalType, string> = {
  none: 'No medical',
  basicmed: 'BasicMed',
  first: 'Class 1',
  second: 'Class 2',
  third: 'Class 3',
};

/**
 * One line that answers "what medical, good until when?".
 *
 * A member with no medical on file reads `No medical on file`.  A medical that
 * has run out reads `Medical expired 2026/01/31`, or `No medical expiry on
 * file` when the class was entered but the date never was.  A current one
 * names the class and the date it runs to, `Class 3 medical to 2027/03/31`.
 */
export function medicalSummary(medical: LeaderMedical): string {
  if (medical.type === 'none') return 'No medical on file';
  if (!medical.is_current) {
    return medical.expiration === null
      ? 'No medical expiry on file'
      : `Medical expired ${formatDate(medical.expiration)}`;
  }
  const phrase = MEDICAL_PHRASES[medical.type];
  return medical.expiration === null
    ? `${phrase} medical`
    : `${phrase} medical to ${formatDate(medical.expiration)}`;
}
