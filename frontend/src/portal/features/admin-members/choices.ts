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
export { certificateLabel, medicalLabel } from '@/portal/choices';

export const ROLE_CHOICES: Choice<RoleSlug>[] = [
  { value: 'member', label: 'Member' },
  { value: 'dart_leader', label: 'DART leader' },
  { value: 'user_admin', label: 'User administrator' },
  { value: 'account_admin', label: 'Account administrator' },
  { value: 'website_admin', label: 'Website administrator' },
  { value: 'system_admin', label: 'System administrator' },
];

export const STATUS_CHOICES: Choice<'current' | 'expired' | 'none'>[] = [
  { value: 'current', label: 'Current' },
  { value: 'expired', label: 'Expired' },
  { value: 'none', label: 'Never a member' },
];

export const TERM_STATUS_CHOICES: Choice<'active' | 'expired' | 'canceled'>[] = [
  { value: 'active', label: 'Active' },
  { value: 'expired', label: 'Expired' },
  { value: 'canceled', label: 'Canceled' },
];

/** The display label for a role slug, or the slug itself if it is not a known role. */
export const roleLabel = (value: string): string => labelFor(ROLE_CHOICES, value);
