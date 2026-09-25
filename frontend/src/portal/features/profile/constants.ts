/**
 * Option lists for the profile form.
 *
 * The coded aviation vocabularies (certificate, IFR, medical, ratings) are the
 * portal's shared ones from `@/portal/choices`, re-exported here so the form
 * and every admin screen that already imports from this module keep one
 * wording per code.  The county list is shared too, since the member filters
 * offer it, and lives in `@/portal/choices`.  Only the volunteer interests
 * belong to this form alone.
 */
export { CERTIFICATE_TYPES, IFR_OPTIONS, MEDICAL_TYPES, RATINGS } from '@/portal/choices';
export type { Choice } from '@/portal/choices';

export const VOLUNTEER_INTERESTS = [
  { field: 'vol_mission_pilot', label: 'Mission pilot' },
  { field: 'vol_ground_team', label: 'Ground support' },
  { field: 'vol_exercise_training', label: 'Exercises and training' },
  { field: 'vol_member_support', label: 'Member support' },
  { field: 'vol_fundraising', label: 'Fundraising' },
  { field: 'vol_social_media', label: 'Social media' },
  { field: 'vol_newsletter', label: 'Newsletter' },
] as const;
