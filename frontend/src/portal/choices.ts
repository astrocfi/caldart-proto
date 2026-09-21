/**
 * The portal's one vocabulary for the coded profile fields.
 *
 * Every screen that shows a certificate, medical, IFR or rating code reads its
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
  IfrRated,
  MedicalType,
  PaymentProvider,
  PaymentState,
  PaymentWallet,
  PilotCertificateType,
  Rating,
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

export const RATINGS: Choice<Rating>[] = [
  { value: 'instrument', label: 'Instrument' },
  { value: 'multi_engine', label: 'Multi-engine' },
  { value: 'cfi', label: 'CFI' },
  { value: 'cfii', label: 'CFII' },
  { value: 'mei', label: 'MEI' },
  { value: 'seaplane', label: 'Seaplane' },
  { value: 'helicopter', label: 'Helicopter' },
  { value: 'glider', label: 'Glider' },
];

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
};

export const PAYMENT_STATUS_LABELS: Record<PaymentState, string> = {
  pending: 'Pending',
  succeeded: 'Succeeded',
  failed: 'Failed',
  refunded: 'Refunded',
};

export const PAYMENT_WALLET_LABELS: Record<PaymentWallet, string> = {
  card: 'Card',
  apple_pay: 'Apple Pay',
  google_pay: 'Google Pay',
  link: 'Link',
  paypal: 'PayPal',
  mock: 'Test',
  unknown: '—',
};
