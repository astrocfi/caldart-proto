/**
 * The profile form's state, validation and wire format.
 *
 * Kept apart from the component so the join wizard and `/profile` share one
 * definition of "is this filled in correctly", and so the rules can be tested
 * without rendering anything.  They mirror the server rules in
 * `members/api/profile_serializers.py`; the server remains authoritative.
 */
import { ApiError } from '../../api/client';
import type {
  IfrRated,
  MedicalType,
  PilotCertificateType,
  Profile,
  ProfilePatch,
  Rating,
} from '../../api/types';

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
  /* contact */
  phone: string;
  phone_alt: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  county: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  /* aviation */
  home_airport_identifier: string;
  home_airport_city: string;
  /** Empty string means "no DART chosen". */
  dart_id: string;
  air_care_alliance_number: string;
  pilot_certificate_type: PilotCertificateType;
  certificate_number: string;
  ifr_rated: IfrRated;
  ratings: Rating[];
  medical_type: MedicalType;
  medical_expiration: string;
  flight_review_date: string;
  total_hours: string;
  /* volunteer interests */
  vol_ground_team: boolean;
  vol_exercise_training: boolean;
  vol_member_support: boolean;
  vol_fundraising: boolean;
  vol_social_media: boolean;
  vol_newsletter: boolean;
}

export type ProfileFormErrors = Partial<Record<keyof ProfileFormValues, string>>;

export const EMPTY_PROFILE_FORM: ProfileFormValues = {
  phone: '',
  phone_alt: '',
  address_line1: '',
  address_line2: '',
  city: '',
  state: 'CA',
  postal_code: '',
  county: '',
  emergency_contact_name: '',
  emergency_contact_phone: '',
  home_airport_identifier: '',
  home_airport_city: '',
  dart_id: '',
  air_care_alliance_number: '',
  pilot_certificate_type: 'none',
  certificate_number: '',
  ifr_rated: 'na',
  ratings: [],
  medical_type: 'none',
  medical_expiration: '',
  flight_review_date: '',
  total_hours: '',
  vol_ground_team: false,
  vol_exercise_training: false,
  vol_member_support: false,
  vol_fundraising: false,
  vol_social_media: false,
  vol_newsletter: false,
};

/** Turn the API's profile into editable form values. */
export function profileToForm(profile: Profile): ProfileFormValues {
  return {
    phone: profile.phone,
    phone_alt: profile.phone_alt,
    address_line1: profile.address_line1,
    address_line2: profile.address_line2,
    city: profile.city,
    state: profile.state || 'CA',
    postal_code: profile.postal_code,
    county: profile.county,
    emergency_contact_name: profile.emergency_contact_name,
    emergency_contact_phone: profile.emergency_contact_phone,
    home_airport_identifier: profile.home_airport_identifier,
    home_airport_city: profile.home_airport_city,
    dart_id: profile.dart ? String(profile.dart.id) : '',
    air_care_alliance_number: profile.air_care_alliance_number,
    pilot_certificate_type: profile.pilot_certificate_type,
    certificate_number: profile.certificate_number,
    ifr_rated: profile.ifr_rated,
    ratings: profile.ratings,
    medical_type: profile.medical_type,
    medical_expiration: profile.medical_expiration ?? '',
    flight_review_date: profile.flight_review_date ?? '',
    total_hours: profile.total_hours === null ? '' : String(profile.total_hours),
    vol_ground_team: profile.vol_ground_team,
    vol_exercise_training: profile.vol_exercise_training,
    vol_member_support: profile.vol_member_support,
    vol_fundraising: profile.vol_fundraising,
    vol_social_media: profile.vol_social_media,
    vol_newsletter: profile.vol_newsletter,
  };
}

/** The body of a `PUT /me/profile`: every writable field, blanks included. */
export function formToPatch(values: ProfileFormValues): ProfilePatch {
  const hours = values.total_hours.trim();
  return {
    phone: values.phone.trim(),
    phone_alt: values.phone_alt.trim(),
    address_line1: values.address_line1.trim(),
    address_line2: values.address_line2.trim(),
    city: values.city.trim(),
    state: values.state.trim().toUpperCase(),
    postal_code: values.postal_code.trim(),
    county: values.county.trim(),
    emergency_contact_name: values.emergency_contact_name.trim(),
    emergency_contact_phone: values.emergency_contact_phone.trim(),
    home_airport_identifier: values.home_airport_identifier.trim().toUpperCase(),
    home_airport_city: values.home_airport_city.trim(),
    dart_id: values.dart_id === '' ? null : Number(values.dart_id),
    air_care_alliance_number: values.air_care_alliance_number.trim(),
    pilot_certificate_type: values.pilot_certificate_type,
    certificate_number: values.certificate_number.trim(),
    ifr_rated: values.ifr_rated,
    ratings: values.ratings,
    medical_type: values.medical_type,
    medical_expiration: values.medical_expiration || null,
    flight_review_date: values.flight_review_date || null,
    total_hours: hours === '' ? null : Number(hours),
    vol_ground_team: values.vol_ground_team,
    vol_exercise_training: values.vol_exercise_training,
    vol_member_support: values.vol_member_support,
    vol_fundraising: values.vol_fundraising,
    vol_social_media: values.vol_social_media,
    vol_newsletter: values.vol_newsletter,
  };
}

const STATE_RE = /^[A-Za-z]{2}$/;
const POSTAL_RE = /^\d{5}(-\d{4})?$/;

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
  'phone',
  'address_line1',
  'city',
  'postal_code',
  'pilot_certificate_type',
] as const satisfies readonly (keyof ProfileFormValues)[];

const REQUIRED_MESSAGES: Record<(typeof REQUIRED_PROFILE_FIELDS)[number], string> = {
  phone: 'A phone number is required.',
  address_line1: 'Your street address is required.',
  city: 'Your city is required.',
  postal_code: 'Your ZIP code is required.',
  pilot_certificate_type: 'Choose a certificate, or "Not a pilot".',
};

/**
 * Inline validation.
 *
 * The required fields are exactly what makes a profile "complete" for the
 * dashboard nudge and the join wizard; the rest of the rules are the server's,
 * checked here so the member sees them without a round trip.
 */
export function validateProfileForm(values: ProfileFormValues): ProfileFormErrors {
  const errors: ProfileFormErrors = {};

  for (const field of REQUIRED_PROFILE_FIELDS) {
    if (!String(values[field] ?? '').trim()) errors[field] = REQUIRED_MESSAGES[field];
  }

  const state = values.state.trim();
  if (state && !STATE_RE.test(state)) {
    errors.state = 'Use the two-letter state code, for example CA.';
  }

  const postal = values.postal_code.trim();
  if (postal && !POSTAL_RE.test(postal)) {
    errors.postal_code = 'Use a ZIP code like 95035 or 95035-1234.';
  }

  if (values.medical_type !== 'none' && !values.medical_expiration) {
    errors.medical_expiration = 'Give the expiration date of your medical certificate.';
  }

  if (values.pilot_certificate_type !== 'none' && !values.certificate_number.trim()) {
    errors.certificate_number = 'Give your pilot certificate number.';
  }

  const hours = values.total_hours.trim();
  if (hours !== '' && !/^\d+$/.test(hours)) {
    errors.total_hours = 'Enter your total hours as a whole number.';
  }

  return errors;
}
