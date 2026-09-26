/**
 * The donation form's values, the checks run before a gift is started, and the body
 * those values become.
 *
 * The required four are checked here the way the server checks them, so the giver
 * hears about a typo before anything is paid; the server still has the last word.
 */
import { ApiError } from '@/portal/api/client';
import type { IfrRated, PilotCertificateType } from '@/portal/api/types';
import { normalizePhone } from '@/portal/features/profile/form';
import { VOLUNTEER_INTERESTS } from '@/portal/features/profile/constants';
import { EMAIL_MESSAGE, isEmailAddress } from '@/portal/masks';
import type { DonorBody } from './api';

/** A volunteer checkbox's field name. */
export type VolunteerField = (typeof VOLUNTEER_INTERESTS)[number]['field'];

/** Everything the form holds, as the inputs hold it. */
export interface DonationFormValues {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  county: string;
  home_airport_identifier: string;
  home_airport_city: string;
  /** The DART's id as the select holds it, or `''` for none. */
  dart_id: string;
  air_care_alliance_number: string;
  pilot_certificate_type: PilotCertificateType;
  ifr_rated: IfrRated;
  volunteer: Record<VolunteerField, boolean>;
}

/** The free-text optional fields, sent only when the giver typed something. */
const OPTIONAL_TEXT = [
  'address_line1',
  'address_line2',
  'city',
  'postal_code',
  'home_airport_identifier',
  'home_airport_city',
  'air_care_alliance_number',
] as const;

/** A form nobody has typed in yet. */
export const EMPTY_DONATION_FORM: DonationFormValues = {
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  address_line1: '',
  address_line2: '',
  city: '',
  state: '',
  postal_code: '',
  county: '',
  home_airport_identifier: '',
  home_airport_city: '',
  dart_id: '',
  air_care_alliance_number: '',
  pilot_certificate_type: 'none',
  ifr_rated: 'na',
  volunteer: Object.fromEntries(VOLUNTEER_INTERESTS.map(({ field }) => [field, false])) as Record<
    VolunteerField,
    boolean
  >,
};

/** A message per field that stops the gift, keyed as the form's own fields are. */
export type DonationFormErrors = Partial<Record<'amount' | keyof DonationFormValues, string>>;

/** What the phone field says when it cannot be read as ten digits. */
export const PHONE_MESSAGE = 'Use a ten-digit number like 415-555-0100.';

/** What the amount says when nothing has been chosen. */
export const AMOUNT_MESSAGE = 'Choose an amount to give.';

/**
 * The reasons `values` and `amountCents` cannot start a gift, empty when they can.
 *
 * An amount, both names, an address that reads as one, and a ten-digit phone number
 * are required; nothing optional is checked here.
 */
export function validateDonation(
  values: DonationFormValues,
  amountCents: number,
): DonationFormErrors {
  const errors: DonationFormErrors = {};
  if (amountCents <= 0) errors.amount = AMOUNT_MESSAGE;
  if (values.first_name.trim() === '') errors.first_name = 'Give your first name.';
  if (values.last_name.trim() === '') errors.last_name = 'Give your last name.';
  if (!isEmailAddress(values.email)) errors.email = EMAIL_MESSAGE;
  if (!/^\d{3}-\d{3}-\d{4}$/.test(normalizePhone(values.phone))) errors.phone = PHONE_MESSAGE;
  return errors;
}

/**
 * The giver's part of the checkout body: the four required fields, then each optional
 * one the giver filled in.
 *
 * A blank field, an unticked box, and a select left on its default are left out, so
 * a returning donor's earlier answers are not cleared by a gift that skips them.
 */
export function donorBody(values: DonationFormValues): DonorBody {
  const body: DonorBody = {
    first_name: values.first_name.trim(),
    last_name: values.last_name.trim(),
    email: values.email.trim(),
    phone: normalizePhone(values.phone),
  };
  for (const key of OPTIONAL_TEXT) {
    const value = values[key].trim();
    if (value !== '') body[key] = value;
  }
  if (values.state !== '') body.state = values.state as DonorBody['state'];
  if (values.county !== '') body.county = values.county as DonorBody['county'];
  if (values.dart_id !== '') body.dart_id = Number(values.dart_id);
  if (values.pilot_certificate_type !== 'none') {
    body.pilot_certificate_type = values.pilot_certificate_type;
  }
  if (values.ifr_rated !== 'na') body.ifr_rated = values.ifr_rated;
  for (const { field } of VOLUNTEER_INTERESTS) {
    if (values.volunteer[field]) body[field] = true;
  }
  return body;
}

/**
 * The form fields the server can refuse a checkout on, keyed as it keys them.
 *
 * `dart_id`, unlike the other form fields, is already the request body's own name,
 * so no renaming is needed to read the server's refusal back onto the field.
 */
const DONOR_FORM_FIELDS: readonly (keyof DonationFormValues)[] = [
  'first_name',
  'last_name',
  'email',
  'phone',
  'address_line1',
  'address_line2',
  'city',
  'state',
  'postal_code',
  'county',
  'home_airport_identifier',
  'home_airport_city',
  'dart_id',
  'air_care_alliance_number',
  'pilot_certificate_type',
  'ifr_rated',
];

/**
 * The message for each of the form's own fields that `caught` refused, if any.
 *
 * `ApiError.fieldErrors` reads every string-valued key of the response body, which
 * would also pick up a sibling ``code`` such as ``has_account``; this narrows that
 * down to the fields the donation form can show an error beside.  Anything else --
 * a refusal with no such field, or a rejection that is not an `ApiError` at all --
 * answers empty.
 */
export function donorFieldErrors(
  caught: unknown,
): Partial<Record<keyof DonationFormValues, string>> {
  if (!(caught instanceof ApiError)) return {};
  const found: Partial<Record<keyof DonationFormValues, string>> = {};
  for (const field of DONOR_FORM_FIELDS) {
    const message = caught.fieldErrors[field];
    if (message !== undefined) found[field] = message;
  }
  return found;
}
