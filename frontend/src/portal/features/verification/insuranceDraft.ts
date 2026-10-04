/**
 * The insurance verification panel's state and the request it sends.
 *
 * Amounts are typed in dollars and sent in integer cents, as the aircraft form does.
 * Changing any insurance field unchecks *Insurance verified*, as the server clears it.
 */
import type { AircraftDetail, InsuranceVerificationPayload } from '@/portal/api/types';
import { MONEY_ERROR } from '@/portal/features/aircraft/form';
import { centsToDollars, dollarsToCents } from '@/portal/features/aircraft/insurance';

export interface InsuranceDraft {
  insurance_carrier: string;
  insurance_policy_number: string;
  /** Dollars, as typed. */
  liability_per_occurrence: string;
  liability_per_person: string;
  hull: string;
  /** `YYYY-MM-DD`, or empty for no date. */
  insurance_expiration: string;
  verified: boolean;
}

/** A field the panel edits, which is every draft key but the check. */
export type InsuranceField = Exclude<keyof InsuranceDraft, 'verified'>;

/** The dollar fields, each with the API field that holds its cents. */
export const MONEY_FIELDS = {
  liability_per_occurrence: 'insurance_liability_per_occurrence_cents',
  liability_per_person: 'insurance_liability_per_person_cents',
  hull: 'insurance_hull_cents',
} as const;

type MoneyField = keyof typeof MONEY_FIELDS;

/** The draft an aircraft opens the panel with. */
export function draftFromAircraft(aircraft: AircraftDetail): InsuranceDraft {
  return {
    insurance_carrier: aircraft.insurance_carrier,
    insurance_policy_number: aircraft.insurance_policy_number,
    liability_per_occurrence: centsToDollars(aircraft.insurance_liability_per_occurrence_cents),
    liability_per_person: centsToDollars(aircraft.insurance_liability_per_person_cents),
    hull: centsToDollars(aircraft.insurance_hull_cents),
    insurance_expiration: aircraft.insurance_expiration ?? '',
    verified: aircraft.insurance_verification.verified,
  };
}

/** `draft` with `field` set to `value`, unchecked when the value differs from the opening one. */
export function editInsurance(
  draft: InsuranceDraft,
  initial: InsuranceDraft,
  field: InsuranceField,
  value: string,
): InsuranceDraft {
  const next = { ...draft, [field]: value };
  return value === initial[field] ? next : { ...next, verified: false };
}

/** The amounts that are not a sum of money, keyed by the draft field. */
export function validateInsurance(draft: InsuranceDraft): Partial<Record<MoneyField, string>> {
  const errors: Partial<Record<MoneyField, string>> = {};
  for (const field of Object.keys(MONEY_FIELDS) as MoneyField[]) {
    if (draft[field].trim() !== '' && dollarsToCents(draft[field]) === null) {
      errors[field] = MONEY_ERROR;
    }
  }
  return errors;
}

/**
 * True when the draft has a policy to verify: one with an expiry date, as every screen
 * reads *No insurance on file* for a policy without one.
 */
export function isPolicyOnFile(draft: InsuranceDraft): boolean {
  return draft.insurance_expiration !== '';
}

/**
 * The request body: the fields that differ from the ones the panel opened with, and
 * whether the insurance is verified, never verified while no policy is on file.  An untouched field is left out, so it is left
 * alone; a blank liability is no cover and a blank hull no hull value, as on the form.
 */
export function insurancePayload(
  initial: InsuranceDraft,
  draft: InsuranceDraft,
): InsuranceVerificationPayload {
  const changed = (field: InsuranceField): boolean => draft[field] !== initial[field];
  const payload: InsuranceVerificationPayload = {
    verified: draft.verified && isPolicyOnFile(draft),
  };
  if (changed('insurance_carrier')) payload.insurance_carrier = draft.insurance_carrier.trim();
  if (changed('insurance_policy_number')) {
    payload.insurance_policy_number = draft.insurance_policy_number.trim();
  }
  if (changed('liability_per_occurrence')) {
    payload.insurance_liability_per_occurrence_cents =
      dollarsToCents(draft.liability_per_occurrence) ?? 0;
  }
  if (changed('liability_per_person')) {
    payload.insurance_liability_per_person_cents = dollarsToCents(draft.liability_per_person) ?? 0;
  }
  if (changed('hull')) payload.insurance_hull_cents = dollarsToCents(draft.hull);
  if (changed('insurance_expiration')) {
    payload.insurance_expiration = draft.insurance_expiration || null;
  }
  return payload;
}
