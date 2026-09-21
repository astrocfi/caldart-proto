/**
 * The aircraft form's values, validation and payload, in one place.
 *
 * The picker's inline "add a new aircraft" form and the administrator's full
 * edit form render different subsets of the same fields, so they share the
 * conversion between form strings and the API's integer cents.
 */
import type { Aircraft, AircraftPatch, OwnerType } from '../../api/types';
import { centsToDollars, dollarsToCents, normalizeNNumber } from './insurance';

export interface AircraftFormValues {
  n_number: string;
  make: string;
  model: string;
  year: string;
  owner_type: OwnerType;
  owner_name: string;
  owner_contact: string;
  seats: string;
  insurance_carrier: string;
  insurance_policy_number: string;
  liability_per_occurrence: string;
  liability_per_person: string;
  hull: string;
  insurance_expiration: string;
  notes: string;
  is_active: boolean;
}

export const OWNER_TYPE_LABELS: Record<OwnerType, string> = {
  individual: 'Individual',
  fbo: 'FBO',
  club: 'Flying club',
};

export const OWNER_TYPES: OwnerType[] = ['individual', 'fbo', 'club'];

/** A blank form draft, prefilled with `nNumber` when the search suggests one. */
export function emptyAircraftValues(nNumber = ''): AircraftFormValues {
  return {
    n_number: nNumber,
    make: '',
    model: '',
    year: '',
    owner_type: 'individual',
    owner_name: '',
    owner_contact: '',
    seats: '',
    insurance_carrier: '',
    insurance_policy_number: '',
    liability_per_occurrence: '',
    liability_per_person: '',
    hull: '',
    insurance_expiration: '',
    notes: '',
    is_active: true,
  };
}

/** An existing aircraft record as editable form values. */
export function aircraftToValues(aircraft: Aircraft): AircraftFormValues {
  return {
    n_number: aircraft.n_number,
    make: aircraft.make,
    model: aircraft.model,
    year: aircraft.year === null ? '' : String(aircraft.year),
    owner_type: aircraft.owner_type,
    owner_name: aircraft.owner_name,
    owner_contact: aircraft.owner_contact,
    seats: aircraft.seats === null ? '' : String(aircraft.seats),
    insurance_carrier: aircraft.insurance_carrier,
    insurance_policy_number: aircraft.insurance_policy_number,
    liability_per_occurrence: centsToDollars(aircraft.insurance_liability_per_occurrence_cents),
    liability_per_person: centsToDollars(aircraft.insurance_liability_per_person_cents),
    hull: centsToDollars(aircraft.insurance_hull_cents),
    insurance_expiration: aircraft.insurance_expiration ?? '',
    notes: aircraft.notes,
    is_active: aircraft.is_active,
  };
}

const MONEY_FIELDS = ['liability_per_occurrence', 'liability_per_person', 'hull'] as const;

export const MONEY_ERROR = 'Enter an amount of $0 or more.';

/** Client-side checks that mirror the serializer, so mistakes surface early. */
export function validateAircraft(values: AircraftFormValues): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!normalizeNNumber(values.n_number)) {
    errors.n_number = 'Enter a registration, for example N12345.';
  }
  if (!values.make.trim()) errors.make = 'Enter the make, for example Cessna.';
  if (!values.model.trim()) errors.model = 'Enter the model, for example 172S Skyhawk.';
  for (const field of MONEY_FIELDS) {
    const raw = values[field];
    if (raw.trim() && dollarsToCents(raw) === null) errors[field] = MONEY_ERROR;
  }
  const year = values.year.trim();
  if (year && !/^\d{4}$/.test(year)) errors.year = 'Enter a four-digit year.';
  return errors;
}

function optionalNumber(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

/** Form values as the JSON body `POST /aircraft` and `PATCH` expect. */
export function aircraftPayload(values: AircraftFormValues): AircraftPatch {
  return {
    n_number: normalizeNNumber(values.n_number),
    make: values.make.trim(),
    model: values.model.trim(),
    year: optionalNumber(values.year),
    owner_type: values.owner_type,
    owner_name: values.owner_name.trim(),
    owner_contact: values.owner_contact.trim(),
    seats: optionalNumber(values.seats),
    insurance_carrier: values.insurance_carrier.trim(),
    insurance_policy_number: values.insurance_policy_number.trim(),
    insurance_liability_per_occurrence_cents: dollarsToCents(values.liability_per_occurrence) ?? 0,
    insurance_liability_per_person_cents: dollarsToCents(values.liability_per_person) ?? 0,
    insurance_hull_cents: dollarsToCents(values.hull),
    insurance_expiration: values.insurance_expiration || null,
    notes: values.notes,
    is_active: values.is_active,
  };
}
