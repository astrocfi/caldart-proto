/**
 * The coded values the admin screens show that the member's own screens do not.
 *
 * The certificate and medical vocabularies the filter bar and the member list
 * share with `/profile` come from the portal's shared `choices` module through
 * `features/profile/constants`, and are re-exported here so no screen can
 * label the same code differently.
 */
import type { RoleSlug } from '@/portal/api/types';
import { labelFor } from '@/portal/choices';
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

/** The medical filter's own list: every class, plus "Has any medical". */
export const MEDICAL_FILTER_CHOICES: Choice<string>[] = [
  ...MEDICAL_TYPES,
  { value: 'any', label: 'Has any medical' },
];
export { certificateLabel, medicalLabel } from '@/portal/choices';

export const ROLE_CHOICES: Choice<RoleSlug>[] = [
  { value: 'member', label: 'Member' },
  { value: 'dart_leader', label: 'DART leader' },
  { value: 'user_admin', label: 'User administrator' },
  { value: 'account_admin', label: 'Account administrator' },
  { value: 'website_admin', label: 'Website administrator' },
  { value: 'system_admin', label: 'System administrator' },
];

export const STATUS_CHOICES: Choice<'current' | 'new' | 'expired' | 'none'>[] = [
  { value: 'current', label: 'Current' },
  { value: 'new', label: 'Joined, not yet paid' },
  { value: 'expired', label: 'Expired' },
  { value: 'none', label: 'Never a member' },
];

export const TERM_STATUS_CHOICES: Choice<'new' | 'active' | 'expired' | 'canceled'>[] = [
  { value: 'new', label: 'New' },
  { value: 'active', label: 'Active' },
  { value: 'expired', label: 'Expired' },
  { value: 'canceled', label: 'Canceled' },
];

/** The display label for a role slug, or the slug itself if it is not a known role. */
export const roleLabel = (value: string): string => labelFor(ROLE_CHOICES, value);
