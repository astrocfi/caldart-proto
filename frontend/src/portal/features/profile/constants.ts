/** Option lists for the profile form, matching the choices in PLAN §4.2. */
import type { IfrRated, MedicalType, PilotCertificateType, Rating } from '../../api/types';

export const CERTIFICATE_TYPES: { value: PilotCertificateType; label: string }[] = [
  { value: 'none', label: 'Not a pilot' },
  { value: 'student', label: 'Student' },
  { value: 'sport', label: 'Sport' },
  { value: 'recreational', label: 'Recreational' },
  { value: 'private', label: 'Private' },
  { value: 'commercial', label: 'Commercial' },
  { value: 'atp', label: 'Airline transport pilot' },
];

export const IFR_OPTIONS: { value: IfrRated; label: string }[] = [
  { value: 'na', label: 'Not applicable' },
  { value: 'yes', label: 'Yes' },
  { value: 'no', label: 'No' },
];

export const MEDICAL_TYPES: { value: MedicalType; label: string }[] = [
  { value: 'none', label: 'None' },
  { value: 'basicmed', label: 'BasicMed' },
  { value: 'first', label: 'First class' },
  { value: 'second', label: 'Second class' },
  { value: 'third', label: 'Third class' },
];

export const RATINGS: { value: Rating; label: string }[] = [
  { value: 'instrument', label: 'Instrument' },
  { value: 'multi_engine', label: 'Multi-engine' },
  { value: 'cfi', label: 'CFI' },
  { value: 'cfii', label: 'CFII' },
  { value: 'mei', label: 'MEI' },
  { value: 'seaplane', label: 'Seaplane' },
  { value: 'helicopter', label: 'Helicopter' },
  { value: 'glider', label: 'Glider' },
];

export const VOLUNTEER_INTERESTS = [
  { field: 'vol_ground_team', label: 'Ground team' },
  { field: 'vol_exercise_training', label: 'Exercises and training' },
  { field: 'vol_member_support', label: 'Member support' },
  { field: 'vol_fundraising', label: 'Fundraising' },
  { field: 'vol_social_media', label: 'Social media' },
  { field: 'vol_newsletter', label: 'Newsletter' },
] as const;

/** Offered as `<datalist>` suggestions on the free-text county field. */
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
