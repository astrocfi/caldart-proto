/**
 * The portal's one vocabulary for the coded profile fields.
 *
 * Every screen that shows a certificate, medical, IFR, or rating code reads its
 * wording from here: the profile form's `<select>` options, the admin filter
 * bar, the member report screens and the DART leader's status card.  They had
 * drifted apart — "None" against "Not a pilot" against "No certificate on
 * file" for one and the same code — which made the same member look different
 * depending on which screen you were standing in front of.
 *
 * Option order is the order the lists render in, which is why these are arrays
 * rather than records; `labelFor` turns one into a lookup.
 */
import type {
  CaliforniaCounty,
  IfrRated,
  MedicalType,
  PaymentProvider,
  PaymentState,
  PaymentWallet,
  PilotCertificateType,
  Rating,
  RoleSlug,
  UsState,
} from './api/types';

export interface Choice<Value extends string> {
  value: Value;
  label: string;
}

export const CERTIFICATE_TYPES: Choice<PilotCertificateType>[] = [
  { value: 'none', label: 'Not a pilot' },
  { value: 'student', label: 'Student' },
  { value: 'sport', label: 'Sport' },
  { value: 'recreational', label: 'Recreational' },
  { value: 'private', label: 'Private' },
  { value: 'commercial', label: 'Commercial' },
  { value: 'atp', label: 'Airline transport pilot' },
];

export const IFR_OPTIONS: Choice<IfrRated>[] = [
  { value: 'na', label: 'Not applicable' },
  { value: 'yes', label: 'Yes' },
  { value: 'no', label: 'No' },
];

export const MEDICAL_TYPES: Choice<MedicalType>[] = [
  { value: 'none', label: 'None' },
  { value: 'basicmed', label: 'BasicMed' },
  { value: 'first', label: 'First class' },
  { value: 'second', label: 'Second class' },
  { value: 'third', label: 'Third class' },
];

/** Every two-letter state or territory code the profile accepts. */
export const US_STATES: Choice<UsState>[] = [
  { value: 'AL', label: 'Alabama' },
  { value: 'AK', label: 'Alaska' },
  { value: 'AZ', label: 'Arizona' },
  { value: 'AR', label: 'Arkansas' },
  { value: 'CA', label: 'California' },
  { value: 'CO', label: 'Colorado' },
  { value: 'CT', label: 'Connecticut' },
  { value: 'DE', label: 'Delaware' },
  { value: 'DC', label: 'District of Columbia' },
  { value: 'FL', label: 'Florida' },
  { value: 'GA', label: 'Georgia' },
  { value: 'HI', label: 'Hawaii' },
  { value: 'ID', label: 'Idaho' },
  { value: 'IL', label: 'Illinois' },
  { value: 'IN', label: 'Indiana' },
  { value: 'IA', label: 'Iowa' },
  { value: 'KS', label: 'Kansas' },
  { value: 'KY', label: 'Kentucky' },
  { value: 'LA', label: 'Louisiana' },
  { value: 'ME', label: 'Maine' },
  { value: 'MD', label: 'Maryland' },
  { value: 'MA', label: 'Massachusetts' },
  { value: 'MI', label: 'Michigan' },
  { value: 'MN', label: 'Minnesota' },
  { value: 'MS', label: 'Mississippi' },
  { value: 'MO', label: 'Missouri' },
  { value: 'MT', label: 'Montana' },
  { value: 'NE', label: 'Nebraska' },
  { value: 'NV', label: 'Nevada' },
  { value: 'NH', label: 'New Hampshire' },
  { value: 'NJ', label: 'New Jersey' },
  { value: 'NM', label: 'New Mexico' },
  { value: 'NY', label: 'New York' },
  { value: 'NC', label: 'North Carolina' },
  { value: 'ND', label: 'North Dakota' },
  { value: 'OH', label: 'Ohio' },
  { value: 'OK', label: 'Oklahoma' },
  { value: 'OR', label: 'Oregon' },
  { value: 'PA', label: 'Pennsylvania' },
  { value: 'RI', label: 'Rhode Island' },
  { value: 'SC', label: 'South Carolina' },
  { value: 'SD', label: 'South Dakota' },
  { value: 'TN', label: 'Tennessee' },
  { value: 'TX', label: 'Texas' },
  { value: 'UT', label: 'Utah' },
  { value: 'VT', label: 'Vermont' },
  { value: 'VA', label: 'Virginia' },
  { value: 'WA', label: 'Washington' },
  { value: 'WV', label: 'West Virginia' },
  { value: 'WI', label: 'Wisconsin' },
  { value: 'WY', label: 'Wyoming' },
  { value: 'AS', label: 'American Samoa' },
  { value: 'GU', label: 'Guam' },
  { value: 'MP', label: 'Northern Mariana Islands' },
  { value: 'PR', label: 'Puerto Rico' },
  { value: 'VI', label: 'US Virgin Islands' },
];

/**
 * The counties the profile's county field and the member filters offer, in
 * alphabetical order.  It is a California organization.
 */
export const CA_COUNTIES: readonly CaliforniaCounty[] = [
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
];

/** The category and class ratings, which the form shows as its first row. */
export const CATEGORY_RATINGS: Choice<Rating>[] = [
  { value: 'asel', label: 'ASEL' },
  { value: 'amel', label: 'AMEL' },
  { value: 'ases', label: 'ASES' },
  { value: 'ames', label: 'AMES' },
  { value: 'helicopter', label: 'Helicopter' },
  { value: 'instrument', label: 'Instrument' },
];

/** The instructor ratings, which the form shows as its second row. */
export const INSTRUCTOR_RATINGS: Choice<Rating>[] = [
  { value: 'cfi', label: 'CFI' },
  { value: 'cfii', label: 'CFII' },
  { value: 'mei', label: 'MEI' },
];

export const RATINGS: Choice<Rating>[] = [...CATEGORY_RATINGS, ...INSTRUCTOR_RATINGS];

/**
 * What each role is called wherever a person reads it.
 *
 * Nothing in the portal shows a role slug: an underscored, lowercase code is an
 * API value, not a name for a volunteer.  Declaring the labels as a record over
 * `RoleSlug` means a role added to the API cannot reach a screen unlabeled —
 * the record fails to compile until it has a name here.
 */
export const ROLE_LABELS: Record<RoleSlug, string> = {
  member: 'Member',
  dart_leader: 'DART leader',
  user_admin: 'User administrator',
  treasurer: 'Treasurer',
  account_admin: 'Account administrator',
  website_admin: 'Website administrator',
  system_admin: 'System administrator',
};

/**
 * The roles as a choice list, in the order `ROLE_LABELS` declares them, which
 * runs from the role every member holds to the one that holds everything.
 */
export const ROLE_CHOICES: Choice<RoleSlug>[] = (Object.keys(ROLE_LABELS) as RoleSlug[]).map(
  (slug) => ({ value: slug, label: ROLE_LABELS[slug] }),
);

/** The label for one code, or the code itself if the server invents a new one. */
export function labelFor<Value extends string>(
  choices: readonly Choice<Value>[],
  value: string,
): string {
  return choices.find((choice) => choice.value === value)?.label ?? value;
}

/** Every choice list as a `{code: label}` record, for direct indexing. */
function asRecord<Value extends string>(choices: readonly Choice<Value>[]): Record<Value, string> {
  return Object.fromEntries(choices.map((c) => [c.value, c.label])) as Record<Value, string>;
}

export const CERTIFICATE_LABELS = asRecord(CERTIFICATE_TYPES);
export const MEDICAL_LABELS = asRecord(MEDICAL_TYPES);
export const RATING_LABELS = asRecord(RATINGS);

/**
 * IFR read *on its own*.
 *
 * `IFR_OPTIONS` answers the form's question — "IFR rated? Yes / No / Not
 * applicable" — which is meaningless printed alone on a status card, where the
 * value has to say what it means without the question.  Both renderings live
 * here so there is still one file to edit when the wording changes.
 */
export const IFR_LABELS: Record<IfrRated, string> = {
  na: 'Not stated',
  yes: 'IFR',
  no: 'VFR only',
};

/** The label for a certificate type code. */
export const certificateLabel = (value: string): string => labelFor(CERTIFICATE_TYPES, value);
/** The label for a medical type code. */
export const medicalLabel = (value: string): string => labelFor(MEDICAL_TYPES, value);
/** The display label for a role slug, or the slug itself if it is not a known role. */
export const roleLabel = (value: string): string => labelFor(ROLE_CHOICES, value);

/** Ratings as one readable phrase, e.g. "Instrument, Multi-engine". */
export function ratingLabels(ratings: readonly Rating[]): string {
  return ratings.map((rating) => RATING_LABELS[rating] ?? rating).join(', ');
}

/* ------------------------------------------------------------- payments */

/**
 * Short names for the payment enums.
 *
 * The checkout's own `PROVIDER_LABELS` is a different thing — it describes
 * what a provider *offers* ("Card · Apple Pay · Google Pay") to label a tab.
 * These name the provider itself, for a table cell or a filter.
 */
export const PAYMENT_PROVIDER_LABELS: Record<PaymentProvider, string> = {
  stripe: 'Stripe',
  paypal: 'PayPal',
  mock: 'Test',
  manual: 'By hand',
};

export const PAYMENT_STATUS_LABELS: Record<PaymentState, string> = {
  pending: 'Pending',
  succeeded: 'Succeeded',
  failed: 'Failed',
  partially_refunded: 'Partly refunded',
  refunded: 'Refunded',
};

export const PAYMENT_WALLET_LABELS: Record<PaymentWallet, string> = {
  card: 'Card',
  apple_pay: 'Apple Pay',
  google_pay: 'Google Pay',
  link: 'Link',
  paypal: 'PayPal',
  mock: 'Test',
  check: 'Check',
  cash: 'Cash',
  bank_transfer: 'Bank transfer',
  other: 'Other',
  unknown: '—',
};
