/**
 * How an FAA registration fills the aircraft form: the owner type a registrant
 * maps to, and the form after a type is picked or a registration is found.
 */
import type { AircraftType, OwnerType, RegistrantType, Registration } from '@/portal/api/types';
import type { AircraftFormValues } from './form';

/**
 * The register's owner type for a registrant: a person or co-owners are an
 * individual, a partnership is a flying club, and a company is an FBO.  A
 * government or unknown registrant has no match, and leaves the owner type be.
 */
const OWNER_TYPE_FOR_REGISTRANT: Record<RegistrantType, OwnerType | null> = {
  individual: 'individual',
  co_owned: 'individual',
  non_citizen_co_owned: 'individual',
  partnership: 'club',
  corporation: 'fbo',
  llc: 'fbo',
  non_citizen_corporation: 'fbo',
  government: null,
  unknown: null,
};

/** The register's owner type for `registrant`, or null when none fits. */
export function ownerTypeForRegistrant(registrant: RegistrantType): OwnerType | null {
  return OWNER_TYPE_FOR_REGISTRANT[registrant];
}

/**
 * The form with `type` picked: the type set, the seats filled from it when the
 * seats box is blank and the type knows its seats, and the category set to the
 * type's when the type has one.  A null `type` clears the type and leaves the
 * seats and the category as they are.
 */
export function withPickedType(
  values: AircraftFormValues,
  type: AircraftType | null,
): AircraftFormValues {
  const fillSeats = type !== null && type.seats !== null && values.seats.trim() === '';
  const category = type === null || type.category === '' ? values.category : type.category;
  return { ...values, type, category, seats: fillSeats ? String(type.seats) : values.seats };
}

/**
 * The form filled from `registration`: the type, the year, the seats, the
 * category, the airworthiness, the owner's name, and the owner type.  Anything
 * the registry does not say (no year, no seats or category on the type, no
 * airworthiness certificate, a registrant with no matching owner type) keeps
 * what the form held.  The other fields are untouched.
 */
export function withRegistration(
  values: AircraftFormValues,
  registration: Registration,
): AircraftFormValues {
  const {
    type,
    year,
    airworthiness,
    registrant_name: ownerName,
    registrant_type: registrant,
  } = registration;
  return {
    ...values,
    type,
    category: type.category === '' ? values.category : type.category,
    airworthiness: airworthiness === '' ? values.airworthiness : airworthiness,
    year: year === null ? values.year : String(year),
    seats: type.seats === null ? values.seats : String(type.seats),
    owner_name: ownerName.trim() === '' ? values.owner_name : ownerName,
    owner_type: ownerTypeForRegistrant(registrant) ?? values.owner_type,
  };
}
