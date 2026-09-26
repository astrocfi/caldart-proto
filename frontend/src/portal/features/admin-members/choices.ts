/**
 * The coded values the admin screens show that the member's own screens do not.
 *
 * The certificate and medical vocabularies the filter bar and the member list
 * share with `/profile` come from the portal's shared `choices` module through
 * `features/profile/constants`, and are re-exported here so no screen can
 * label the same code differently.  The role names and the membership status
 * labels come from the same shared module, so the member screens, the member
 * report, and the DART leader's status card all agree on them.
 */
import type { MembershipTermStatus } from '@/portal/api/types';
import type { Choice } from '@/portal/choices';
import { CERTIFICATE_TYPES, MEDICAL_TYPES } from '@/portal/features/profile/constants';

export { CERTIFICATE_TYPES, MEDICAL_TYPES };

/**
 * The certificate filter's own list: every certificate, plus "Any licensed"
 * for the five a pilot may act on alone.
 *
 * It sits directly after "Student" because that is where the line falls: a
 * student certificate is not one anybody flies a mission on.
 */
export const CERTIFICATE_FILTER_CHOICES: Choice<string>[] = [
  ...CERTIFICATE_TYPES.slice(0, 2),
  { value: 'licensed', label: 'Any licensed' },
  ...CERTIFICATE_TYPES.slice(2),
];

/**
 * The kind selector's choices.  Its blank first option, **All**, lists members
 * and friends together; a donor is in no member list, so is never offered.
 */
export const KIND_FILTER_CHOICES: Choice<'member' | 'friend'>[] = [
  { value: 'member', label: 'Members only' },
  { value: 'friend', label: 'Friends only' },
];

/** The medical filter's own list: every class, plus "Has any medical". */
export const MEDICAL_FILTER_CHOICES: Choice<string>[] = [
  ...MEDICAL_TYPES,
  { value: 'any', label: 'Has any medical' },
];

export {
  certificateLabel,
  medicalLabel,
  roleLabel,
  ROLE_CHOICES,
  MEMBERSHIP_STATUS_CHOICES as STATUS_CHOICES,
} from '@/portal/choices';

export const TERM_STATUS_CHOICES: Choice<MembershipTermStatus>[] = [
  { value: 'active', label: 'Active' },
  { value: 'expired', label: 'Expired' },
  { value: 'canceled', label: 'Canceled' },
  { value: 'suspended', label: 'Suspended' },
];
