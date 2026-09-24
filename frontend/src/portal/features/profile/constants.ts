/**
 * Option lists for the profile form.
 *
 * The coded aviation vocabularies (certificate, IFR, medical, ratings) are the
 * portal's shared ones from `@/portal/choices`, re-exported here so the form
 * and every admin screen that already imports from this module keep one
 * wording per code.  Only the lists that belong to this form alone —
 * volunteer interests and the county suggestions — are defined below.
 */
export { CERTIFICATE_TYPES, IFR_OPTIONS, MEDICAL_TYPES, RATINGS } from '@/portal/choices';
export type { Choice } from '@/portal/choices';

export const VOLUNTEER_INTERESTS = [
  { field: 'vol_mission_pilot', label: 'Mission pilot' },
  { field: 'vol_ground_team', label: 'Ground team' },
  { field: 'vol_exercise_training', label: 'Exercises and training' },
  { field: 'vol_member_support', label: 'Member support' },
  { field: 'vol_fundraising', label: 'Fundraising' },
  { field: 'vol_social_media', label: 'Social media' },
  { field: 'vol_newsletter', label: 'Newsletter' },
] as const;

/** The counties the county field offers.  It is a California organization. */
export const CA_COUNTIES = [
  'Alameda',
  'Alpine',
  'Amador',
  'Butte',
  'Calaveras',
  'Colusa',
  'Contra Costa',
  'Del Norte',
  'El Dorado',
  'Fresno',
  'Glenn',
  'Humboldt',
  'Imperial',
  'Inyo',
  'Kern',
  'Kings',
  'Lake',
  'Lassen',
  'Los Angeles',
  'Madera',
  'Marin',
  'Mariposa',
  'Mendocino',
  'Merced',
  'Modoc',
  'Mono',
  'Monterey',
  'Napa',
  'Nevada',
  'Orange',
  'Placer',
  'Plumas',
  'Riverside',
  'Sacramento',
  'San Benito',
  'San Bernardino',
  'San Diego',
  'San Francisco',
  'San Joaquin',
  'San Luis Obispo',
  'San Mateo',
  'Santa Barbara',
  'Santa Clara',
  'Santa Cruz',
  'Shasta',
  'Sierra',
  'Siskiyou',
  'Solano',
  'Sonoma',
  'Stanislaus',
  'Sutter',
  'Tehama',
  'Trinity',
  'Tulare',
  'Tuolumne',
  'Ventura',
  'Yolo',
  'Yuba',
] as const;
