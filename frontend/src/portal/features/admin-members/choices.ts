/**
 * Human labels for the coded fields in PLAN §4.1 and §4.2.
 *
 * The API returns slugs; every screen in this feature reads its wording from
 * here so a filter dropdown and a profile form can never disagree.
 */
import type { MedicalType, PilotCertificateType, Rating, RoleSlug } from '../../api/types';

export interface Choice<Value extends string> {
  value: Value;
  label: string;
}

export const CERTIFICATE_CHOICES: Choice<PilotCertificateType>[] = [
  { value: 'none', label: 'None' },
  { value: 'student', label: 'Student' },
  { value: 'sport', label: 'Sport' },
  { value: 'recreational', label: 'Recreational' },
  { value: 'private', label: 'Private' },
  { value: 'commercial', label: 'Commercial' },
  { value: 'atp', label: 'Airline transport pilot' },
];

export const MEDICAL_CHOICES: Choice<MedicalType>[] = [
  { value: 'none', label: 'None' },
  { value: 'basicmed', label: 'BasicMed' },
  { value: 'first', label: 'First class' },
  { value: 'second', label: 'Second class' },
  { value: 'third', label: 'Third class' },
];

export const IFR_CHOICES: Choice<'na' | 'yes' | 'no'>[] = [
  { value: 'na', label: 'Not applicable' },
  { value: 'yes', label: 'Yes' },
  { value: 'no', label: 'No' },
];

export const RATING_CHOICES: Choice<Rating>[] = [
  { value: 'instrument', label: 'Instrument' },
  { value: 'multi_engine', label: 'Multi-engine' },
  { value: 'cfi', label: 'CFI' },
  { value: 'cfii', label: 'CFII' },
  { value: 'mei', label: 'MEI' },
  { value: 'seaplane', label: 'Seaplane' },
  { value: 'helicopter', label: 'Helicopter' },
  { value: 'glider', label: 'Glider' },
];

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

/** The six volunteer-interest booleans, in the order the join form asks them. */
export const VOLUNTEER_FIELDS = [
  { name: 'vol_ground_team', label: 'Ground team' },
  { name: 'vol_exercise_training', label: 'Exercises and training' },
  { name: 'vol_member_support', label: 'Member support' },
  { name: 'vol_fundraising', label: 'Fundraising' },
  { name: 'vol_social_media', label: 'Social media' },
  { name: 'vol_newsletter', label: 'Newsletter' },
] as const;

export type VolunteerField = (typeof VOLUNTEER_FIELDS)[number]['name'];

function labelFrom<Value extends string>(choices: Choice<Value>[], value: string): string {
  return choices.find((choice) => choice.value === value)?.label ?? value;
}

export const certificateLabel = (value: string) => labelFrom(CERTIFICATE_CHOICES, value);
export const medicalLabel = (value: string) => labelFrom(MEDICAL_CHOICES, value);
export const roleLabel = (value: string) => labelFrom(ROLE_CHOICES, value);
