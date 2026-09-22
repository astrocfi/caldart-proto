import { describe, expect, it } from 'vitest';

import { makeProfile } from '@test/fixtures/profile';
import {
  EMPTY_PROFILE_FORM,
  REQUIRED_PROFILE_FIELDS,
  formToPatch,
  profileToForm,
  validateProfileForm,
} from './form';

describe('profileToForm', () => {
  it('flattens the nested dart onto the select value', () => {
    expect(profileToForm(makeProfile()).dart_id).toBe('1');
    expect(profileToForm(makeProfile({ dart: null })).dart_id).toBe('');
  });

  it('turns nullable numbers and dates into empty strings', () => {
    const values = profileToForm(
      makeProfile({ total_hours: null, medical_expiration: null, flight_review_date: null }),
    );
    expect(values.total_hours).toBe('');
    expect(values.medical_expiration).toBe('');
    expect(values.flight_review_date).toBe('');
  });

  it('defaults a blank state to CA', () => {
    expect(profileToForm(makeProfile({ state: '' })).state).toBe('CA');
  });
});

describe('formToPatch', () => {
  it('sends every writable field so PUT is a real full update', () => {
    const patch = formToPatch(profileToForm(makeProfile()));
    expect(patch.phone).toBe('650-555-0101');
    expect(patch.dart_id).toBe(1);
    expect(patch.ratings).toEqual(['instrument']);
    expect(patch.total_hours).toBe(750);
    expect(patch.vol_ground_team).toBe(false);
  });

  it('nulls the empty date, hour and dart values', () => {
    const patch = formToPatch({ ...EMPTY_PROFILE_FORM, phone: '555-0100' });
    expect(patch.dart_id).toBeNull();
    expect(patch.medical_expiration).toBeNull();
    expect(patch.flight_review_date).toBeNull();
    expect(patch.total_hours).toBeNull();
  });

  it('trims and upper-cases what the server would anyway', () => {
    const patch = formToPatch({
      ...EMPTY_PROFILE_FORM,
      phone: '  555-0100  ',
      state: 'ca',
      home_airport_identifier: 'pao',
    });
    expect(patch.phone).toBe('555-0100');
    expect(patch.state).toBe('CA');
    expect(patch.home_airport_identifier).toBe('PAO');
  });
});

describe('validateProfileForm', () => {
  it('accepts a filled-in profile', () => {
    expect(validateProfileForm(profileToForm(makeProfile()))).toEqual({});
  });

  it('requires exactly the fields that make a profile complete', () => {
    const errors = validateProfileForm({ ...EMPTY_PROFILE_FORM, state: '', postal_code: '' });
    // `pilot_certificate_type` is in the same list but is a select that always
    // holds a value, so it cannot be missing from a rendered form.
    expect(Object.keys(errors).sort()).toEqual(['address_line1', 'city', 'phone', 'postal_code']);
  });

  it('lists the same fields the server calls a complete profile', () => {
    expect([...REQUIRED_PROFILE_FIELDS].sort()).toEqual([
      'address_line1',
      'city',
      'phone',
      'pilot_certificate_type',
      'postal_code',
    ]);
  });

  it('rejects a state that is not two letters', () => {
    expect(validateProfileForm({ ...EMPTY_PROFILE_FORM, state: 'California' }).state).toMatch(
      /two-letter/,
    );
  });

  it('accepts a ZIP and a ZIP+4 but nothing else', () => {
    const base = { ...EMPTY_PROFILE_FORM, phone: '1', city: 'Napa' };
    expect(validateProfileForm({ ...base, postal_code: '94559' }).postal_code).toBeUndefined();
    expect(validateProfileForm({ ...base, postal_code: '94559-1234' }).postal_code).toBeUndefined();
    expect(validateProfileForm({ ...base, postal_code: '9455' }).postal_code).toBeDefined();
  });

  it('wants an expiration date once a medical is claimed', () => {
    const values = { ...profileToForm(makeProfile()), medical_expiration: '' };
    expect(validateProfileForm(values).medical_expiration).toBeDefined();
    expect(
      validateProfileForm({ ...values, medical_type: 'none' }).medical_expiration,
    ).toBeUndefined();
  });

  it('wants a certificate number once a certificate is claimed', () => {
    const values = { ...profileToForm(makeProfile()), certificate_number: '  ' };
    expect(validateProfileForm(values).certificate_number).toBeDefined();
    expect(
      validateProfileForm({ ...values, pilot_certificate_type: 'none' }).certificate_number,
    ).toBeUndefined();
  });

  it('insists that total hours are a whole number', () => {
    const values = profileToForm(makeProfile());
    expect(validateProfileForm({ ...values, total_hours: 'lots' }).total_hours).toBeDefined();
    expect(validateProfileForm({ ...values, total_hours: '' }).total_hours).toBeUndefined();
    expect(validateProfileForm({ ...values, total_hours: '900' }).total_hours).toBeUndefined();
  });
});
