import { describe, expect, it } from 'vitest';

import { makeVerifiedAircraft } from '@test/handlers';
import {
  draftFromAircraft,
  editInsurance,
  insurancePayload,
  validateInsurance,
} from './insuranceDraft';

const INITIAL = draftFromAircraft(makeVerifiedAircraft());

describe('draftFromAircraft', () => {
  it('reads the amounts in dollars and the verified state', () => {
    expect(INITIAL).toEqual({
      insurance_carrier: 'Avemco',
      insurance_policy_number: 'AV-00012345',
      liability_per_occurrence: '1,000,000',
      liability_per_person: '100,000',
      hull: '145,000',
      insurance_expiration: '2027-03-01',
      verified: true,
    });
  });
});

describe('editInsurance', () => {
  it('unticks the insurance when a field changes', () => {
    expect(editInsurance(INITIAL, INITIAL, 'insurance_carrier', 'AIG').verified).toBe(false);
  });

  it('keeps the tick when a field is put back to its opening value', () => {
    const edited = { ...editInsurance(INITIAL, INITIAL, 'hull', '1'), verified: true };
    expect(editInsurance(edited, INITIAL, 'hull', '145,000').verified).toBe(true);
  });
});

describe('insurancePayload', () => {
  it('sends only the verified state when nothing changed', () => {
    expect(insurancePayload(INITIAL, { ...INITIAL, verified: false })).toEqual({
      verified: false,
    });
  });

  it('sends a changed amount in cents', () => {
    const draft = { ...INITIAL, liability_per_person: '250,000' };
    expect(insurancePayload(INITIAL, draft)).toEqual({
      insurance_liability_per_person_cents: 25_000_000,
      verified: true,
    });
  });

  it('sends a blank hull as no hull value and a blank date as null', () => {
    const draft = { ...INITIAL, hull: '', insurance_expiration: '' };
    expect(insurancePayload(INITIAL, draft)).toEqual({
      insurance_hull_cents: null,
      insurance_expiration: null,
      verified: true,
    });
  });
});

describe('validateInsurance', () => {
  it('refuses an amount that is not a sum of money', () => {
    expect(validateInsurance({ ...INITIAL, hull: 'lots' })).toEqual({
      hull: 'Enter an amount of $0 or more.',
    });
  });
});
