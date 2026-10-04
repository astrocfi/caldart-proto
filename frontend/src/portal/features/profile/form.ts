/**
 * The profile form's state, validation, and wire format.
 *
 * Kept apart from the component so the join wizard and `/profile` share one
 * definition of "is this filled in correctly", and so the rules can be tested
 * without rendering anything.  They mirror the server rules in
 * `members/api/profile_serializers.py`; the server remains authoritative.
 */
import { ApiError } from '@/portal/api/client';
import type {
  CaliforniaCounty,
  MedicalType,
  PhotoIdType,
  PilotCertificateType,
  Profile,
  ProfileNameKey,
  ProfilePatch,
  Rating,
  UsState,
} from '@/portal/api/types';

/**
 * What to say in the toast when a save is rejected.
 *
 * Field-level messages are already rendered beside the offending input, so the
 * toast points at them instead of repeating one of them.
 */
export function saveErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (Object.keys(error.fieldErrors).length > 0) {
      return 'Check the highlighted fields and try again.';
    }
    return error.message;
  }
  return 'Your profile was not saved.';
}

export interface ProfileFormValues {
  /* the account's names, shown only on the member's own profile */
  first_name: string;
  last_name: string;
  /* contact */
  phone: string;
  phone_extension: string;
  phone_alt: string;
  phone_alt_extension: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: UsState;
  postal_code: string;
  county: CaliforniaCounty | '';
  emergency_contact_name: string;
  emergency_contact_phone: string;
  emergency_contact_phone_extension: string;
  /* amateur radio */
  ham_callsign: string;
  /* aviation */
  home_airport_identifier: string;
  secondary_airport_identifier: string;
  /** Empty string means "no DART chosen". */
  dart_id: string;
  air_care_alliance_number: string;
  pilot_certificate_type: PilotCertificateType;
  certificate_number: string;
  ratings: Rating[];
  medical_type: MedicalType;
  medical_expiration: string;
  /** Only the kind of document is recorded, never a number or a date. */
  photo_id_type: PhotoIdType;
  flight_review_date: string;
  total_hours: string;
  flies_rented_aircraft: boolean;
  /* volunteer interests */
  vol_mission_pilot: boolean;
  vol_ground_team: boolean;
  vol_exercise_training: boolean;
  vol_member_support: boolean;
  vol_fundraising: boolean;
  vol_social_media: boolean;
  vol_newsletter: boolean;
}

export type ProfileFormErrors = Partial<Record<keyof ProfileFormValues, string>>;

export const EMPTY_PROFILE_FORM: ProfileFormValues = {
  first_name: '',
  last_name: '',
  phone: '',
  phone_extension: '',
  phone_alt: '',
  phone_alt_extension: '',
  address_line1: '',
  address_line2: '',
  city: '',
  state: 'CA',
  postal_code: '',
  county: '',
  emergency_contact_name: '',
  emergency_contact_phone: '',
  emergency_contact_phone_extension: '',
  ham_callsign: '',
  home_airport_identifier: '',
  secondary_airport_identifier: '',
  dart_id: '',
  air_care_alliance_number: '',
  pilot_certificate_type: 'none',
  certificate_number: '',
  ratings: [],
  medical_type: 'none',
  medical_expiration: '',
  photo_id_type: 'not_provided',
  flight_review_date: '',
  total_hours: '',
  flies_rented_aircraft: false,
  vol_mission_pilot: false,
  vol_ground_team: false,
  vol_exercise_training: false,
  vol_member_support: false,
  vol_fundraising: false,
  vol_social_media: false,
  vol_newsletter: false,
};

/**
 * A profile as either API answers it: the member's own carries the names, the member
 * record's nested profile does not.
 */
export type ProfileSource = Omit<Profile, ProfileNameKey> & Partial<Pick<Profile, ProfileNameKey>>;

/** Turn the API's profile into editable form values; absent names read as blank. */
export function profileToForm(profile: ProfileSource): ProfileFormValues {
  const { photo_id_type } = profile;
  return {
    first_name: profile.first_name ?? '',
    last_name: profile.last_name ?? '',
    phone: profile.phone,
    phone_extension: profile.phone_extension,
    phone_alt: profile.phone_alt,
    phone_alt_extension: profile.phone_alt_extension,
    address_line1: profile.address_line1,
    address_line2: profile.address_line2,
    city: profile.city,
    state: profile.state || 'CA',
    postal_code: profile.postal_code,
    county: profile.county,
    emergency_contact_name: profile.emergency_contact_name,
    emergency_contact_phone: profile.emergency_contact_phone,
    emergency_contact_phone_extension: profile.emergency_contact_phone_extension,
    ham_callsign: profile.ham_callsign,
    home_airport_identifier: profile.home_airport_identifier,
    secondary_airport_identifier: profile.secondary_airport_identifier,
    dart_id: profile.dart ? String(profile.dart.id) : '',
    air_care_alliance_number: profile.air_care_alliance_number,
    pilot_certificate_type: profile.pilot_certificate_type,
    certificate_number: profile.certificate_number,
    ratings: profile.ratings,
    medical_type: profile.medical_type,
    medical_expiration: profile.medical_expiration ?? '',
    photo_id_type,
    flight_review_date: profile.flight_review_date ?? '',
    total_hours: profile.total_hours === null ? '' : String(profile.total_hours),
    flies_rented_aircraft: profile.flies_rented_aircraft,
    vol_mission_pilot: profile.vol_mission_pilot,
    vol_ground_team: profile.vol_ground_team,
    vol_exercise_training: profile.vol_exercise_training,
    vol_member_support: profile.vol_member_support,
    vol_fundraising: profile.vol_fundraising,
    vol_social_media: profile.vol_social_media,
    vol_newsletter: profile.vol_newsletter,
  };
}

/**
 * The profile fields of a write: every writable field, blanks included, and never the
 * names, which the member record writes as account fields of its own.
 */
export function formToPatch(values: ProfileFormValues): Omit<ProfilePatch, ProfileNameKey> {
  const hours = values.total_hours.trim();
  return {
    phone: normalizePhone(values.phone),
    phone_extension: values.phone_extension.trim(),
    phone_alt: normalizePhone(values.phone_alt),
    phone_alt_extension: values.phone_alt_extension.trim(),
    address_line1: values.address_line1.trim(),
    address_line2: values.address_line2.trim(),
    city: values.city.trim(),
    state: values.state,
    postal_code: values.postal_code.trim(),
    county: values.county,
    emergency_contact_name: values.emergency_contact_name.trim(),
    emergency_contact_phone: normalizePhone(values.emergency_contact_phone),
    emergency_contact_phone_extension: values.emergency_contact_phone_extension.trim(),
    ham_callsign: maskCallsign(values.ham_callsign),
    home_airport_identifier: values.home_airport_identifier.trim().toUpperCase(),
    secondary_airport_identifier: values.secondary_airport_identifier.trim().toUpperCase(),
    dart_id: values.dart_id === '' ? null : Number(values.dart_id),
    air_care_alliance_number: values.air_care_alliance_number.trim(),
    pilot_certificate_type: values.pilot_certificate_type,
    certificate_number: values.certificate_number.trim(),
    ratings: values.ratings,
    medical_type: values.medical_type,
    medical_expiration: values.medical_expiration || null,
    photo_id_type: values.photo_id_type,
    flight_review_date: values.flight_review_date || null,
    total_hours: hours === '' ? null : Number(hours),
    flies_rented_aircraft: values.flies_rented_aircraft,
    vol_mission_pilot: values.vol_mission_pilot,
    vol_ground_team: values.vol_ground_team,
    vol_exercise_training: values.vol_exercise_training,
    vol_member_support: values.vol_member_support,
    vol_fundraising: values.vol_fundraising,
    vol_social_media: values.vol_social_media,
    vol_newsletter: values.vol_newsletter,
  };
}

/**
 * The body of the member's own `PUT /me/profile`: `formToPatch`, plus the names when the
 * form showed them.
 */
export function formToMemberPatch(values: ProfileFormValues, withNames: boolean): ProfilePatch {
  const patch = formToPatch(values);
  if (!withNames) return patch;
  return { ...patch, first_name: values.first_name.trim(), last_name: values.last_name.trim() };
}

/** The longest US callsign: a two-letter prefix, a digit, and a three-letter suffix. */
const CALLSIGN_LENGTH = 6;

/**
 * A callsign as it is typed and stored: letters and digits only, upper case, at most
 * six characters.
 */
export function maskCallsign(raw: string): string {
  return raw
    .replace(/[^A-Za-z0-9]/g, '')
    .toUpperCase()
    .slice(0, CALLSIGN_LENGTH);
}

/** A US amateur radio callsign, matching `HAM_CALLSIGN_RE` on the server. */
const CALLSIGN_RE = /^(?:[KNW][A-Z]?|A[A-L])[0-9][A-Z]{1,3}$/;

const CALLSIGN_MESSAGE = 'Enter a US amateur radio callsign, such as W6ABC.';

const NAME_MESSAGES: Record<ProfileNameKey, string> = {
  first_name: 'Enter your first name.',
  last_name: 'Enter your last name.',
};

const POSTAL_RE = /^\d{5}$/;
const PHONE_RE = /^\d{3}-\d{3}-\d{4}$/;
const EXTENSION_RE = /^\d{1,6}$/;

/** One identifier as it is stored: three letters or digits. */
const AIRPORT_RE = /^[A-Z0-9]{3}$/;

const EXTENSION_MESSAGE = 'An extension is digits only, for example 4021.';

const AIRPORT_MESSAGE = 'Use a three-character identifier like PAO, E16, or KLS.';

/** The most hours a logbook may claim, matching `MAX_TOTAL_HOURS` on the server. */
export const MAX_TOTAL_HOURS = 99_999;

const PHONE_MESSAGE = 'Use a ten-digit number like 415-555-0100.';

/**
 * A typed number as this system stores it: `XXX-XXX-XXXX`.
 *
 * Punctuation and spaces are dropped and a leading country code `1` with them,
 * so `+1 (415) 555-0100` and `4155550100` both come back `415-555-0100`.
 * Anything that is not ten digits is returned trimmed, for the caller to
 * refuse: this never invents a number.
 */
export function normalizePhone(value: string): string {
  const digits = value.replace(/\D/g, '');
  const ten = digits.length === 11 && digits.startsWith('1') ? digits.slice(1) : digits;
  if (ten.length !== 10) return value.trim();
  return `${ten.slice(0, 3)}-${ten.slice(3, 6)}-${ten.slice(6)}`;
}

/**
 * The fields that make a profile "complete" — the list behind the user payload's
 * `profile_complete` flag, and the same one `MemberProfile.COMPLETE_FIELDS` uses
 * on the server.
 *
 * The wizard cannot ask for less than this (the visitor would be stuck on step
 * 2, because `profile_complete` would still be false) nor more (they would be
 * nagged by a dashboard that thinks they have finished).  `pilot_certificate_type`
 * is a select that always holds a value, so it is listed for the record.
 */
export const REQUIRED_PROFILE_FIELDS = [
  'address_line1',
  'city',
  'state',
  'postal_code',
  'pilot_certificate_type',
] as const satisfies readonly (keyof ProfileFormValues)[];

const REQUIRED_MESSAGES: Record<(typeof REQUIRED_PROFILE_FIELDS)[number], string> = {
  address_line1: 'Enter your street address.',
  city: 'Enter your city.',
  state: 'Choose your state.',
  postal_code: 'Enter your ZIP code.',
  pilot_certificate_type: 'Choose a certificate, or "Not a pilot".',
};

/**
 * Inline validation.
 *
 * The required fields are exactly what makes a profile "complete" for the join
 * wizard and the onboarding guard, plus the two names when the form shows them
 * (`withNames`); the rest of the rules are the server's, checked here so the
 * member sees them without a round trip.
 */
export function validateProfileForm(
  values: ProfileFormValues,
  withNames = false,
): ProfileFormErrors {
  const errors: ProfileFormErrors = {};

  if (withNames) {
    for (const field of ['first_name', 'last_name'] as const) {
      if (values[field].trim() === '') errors[field] = NAME_MESSAGES[field];
    }
  }

  for (const field of REQUIRED_PROFILE_FIELDS) {
    if (!String(values[field] ?? '').trim()) errors[field] = REQUIRED_MESSAGES[field];
  }

  for (const field of ['phone', 'phone_alt', 'emergency_contact_phone'] as const) {
    const typed = values[field].trim();
    if (!typed) continue;
    if (!PHONE_RE.test(normalizePhone(typed))) errors[field] = PHONE_MESSAGE;
  }

  for (const field of [
    'phone_extension',
    'phone_alt_extension',
    'emergency_contact_phone_extension',
  ] as const) {
    const extension = values[field].trim();
    if (extension && !EXTENSION_RE.test(extension)) errors[field] = EXTENSION_MESSAGE;
  }

  for (const field of ['home_airport_identifier', 'secondary_airport_identifier'] as const) {
    const airport = values[field].trim().toUpperCase();
    if (airport && !AIRPORT_RE.test(airport)) errors[field] = AIRPORT_MESSAGE;
  }

  const callsign = maskCallsign(values.ham_callsign);
  if (callsign && !CALLSIGN_RE.test(callsign)) errors.ham_callsign = CALLSIGN_MESSAGE;

  const postal = values.postal_code.trim();
  if (postal && !POSTAL_RE.test(postal)) {
    errors.postal_code = 'Use a 5-digit ZIP code, such as 95035.';
  }

  if (values.medical_type !== 'none' && !values.medical_expiration) {
    errors.medical_expiration = "Enter the medical's expiration date.";
  }

  if (values.pilot_certificate_type !== 'none' && !values.certificate_number.trim()) {
    errors.certificate_number = 'Enter the pilot certificate number.';
  }

  const hours = values.total_hours.trim();
  if (hours !== '' && !/^\d+$/.test(hours)) {
    errors.total_hours = 'Enter your total hours as a whole number.';
  } else if (hours !== '' && Number(hours) > MAX_TOTAL_HOURS) {
    errors.total_hours = `Enter fewer than ${MAX_TOTAL_HOURS.toLocaleString('en-US')} hours.`;
  }

  return errors;
}
