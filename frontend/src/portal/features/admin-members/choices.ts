/**
 * The coded values the admin screens show that the member's own screens do not.
 *
 * The profile vocabularies — certificate, IFR, medical, ratings, volunteer
 * interests, county suggestions — belong to `features/profile/constants`, and
 * are re-exported here so the filter bar, the admin form and `/profile` can
 * never label the same code differently.
 */
import type { RoleSlug } from '../../api/types';
import {
  CERTIFICATE_TYPES,
  IFR_OPTIONS,
  MEDICAL_TYPES,
  RATINGS,
  VOLUNTEER_INTERESTS,
} from '../profile/constants';

export { CA_COUNTIES } from '../profile/constants';
export { CERTIFICATE_TYPES, IFR_OPTIONS, MEDICAL_TYPES, RATINGS, VOLUNTEER_INTERESTS };

export interface Choice<Value extends string> {
  value: Value;
  label: string;
}

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

export const TERM_STATUS_CHOICES: Choice<'active' | 'expired' | 'cancelled'>[] = [
  { value: 'active', label: 'Active' },
  { value: 'expired', label: 'Expired' },
  { value: 'cancelled', label: 'Cancelled' },
];

function labelFrom<Value extends string>(
  choices: readonly { value: Value; label: string }[],
  value: string,
): string {
  return choices.find((choice) => choice.value === value)?.label ?? value;
}

export const certificateLabel = (value: string) => labelFrom(CERTIFICATE_TYPES, value);
export const medicalLabel = (value: string) => labelFrom(MEDICAL_TYPES, value);
export const roleLabel = (value: string) => labelFrom(ROLE_CHOICES, value);
