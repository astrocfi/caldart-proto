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

  it('lists the same fields the server calls a complete profile', () => {
    expect([...REQUIRED_PROFILE_FIELDS].sort()).toEqual([
      'address_line1',
      'city',
      'phone',
      'pilot_certificate_type',
      'postal_code',
    ]);
  });

  // `pilot_certificate_type` is required too, but it is a select that always
  // holds a value, so it cannot be missing from a rendered form.
  it('names every missing required field in its own words', () => {
    const errors = validateProfileForm({ ...EMPTY_PROFILE_FORM, state: '', postal_code: '' });
    expect(errors).toEqual({
      phone: 'A phone number is required.',
      address_line1: 'Your street address is required.',
      city: 'Your city is required.',
      postal_code: 'Your ZIP code is required.',
    });
  });

  it('rejects a state that is not two letters', () => {
    expect(validateProfileForm({ ...EMPTY_PROFILE_FORM, state: 'California' }).state).toBe(
      'Use the two-letter state code, for example CA.',
    );
  });

  const POSTAL_MESSAGE = 'Use a ZIP code like 95035 or 95035-1234.';

  it.each([
    ['94559', undefined],
    ['94559-1234', undefined],
    ['9455', POSTAL_MESSAGE],
    ['945590', POSTAL_MESSAGE],
    ['94559-123', POSTAL_MESSAGE],
    ['94559-12345', POSTAL_MESSAGE],
    ['94559 1234', POSTAL_MESSAGE],
    ['SW1A 1AA', POSTAL_MESSAGE],
  ])('judges the ZIP code %s', (postalCode, expected) => {
    const values = { ...EMPTY_PROFILE_FORM, phone: '1', city: 'Napa', postal_code: postalCode };
    expect(validateProfileForm(values).postal_code).toBe(expected);
  });

  it('wants an expiration date once a medical is claimed', () => {
    const values = { ...profileToForm(makeProfile()), medical_expiration: '' };
    expect(validateProfileForm(values).medical_expiration).toBe(
      'Give the expiration date of your medical certificate.',
    );
  });

  it('leaves the medical expiration alone when there is no medical', () => {
    const values = { ...profileToForm(makeProfile()), medical_expiration: '' };
    expect(
      validateProfileForm({ ...values, medical_type: 'none' }).medical_expiration,
    ).toBeUndefined();
  });

  it('wants a certificate number once a certificate is claimed', () => {
    const values = { ...profileToForm(makeProfile()), certificate_number: '  ' };
    expect(validateProfileForm(values).certificate_number).toBe(
      'Give your pilot certificate number.',
    );
  });

  it('leaves the certificate number alone for someone who is not a pilot', () => {
    const values = { ...profileToForm(makeProfile()), certificate_number: '  ' };
    expect(
      validateProfileForm({ ...values, pilot_certificate_type: 'none' }).certificate_number,
    ).toBeUndefined();
  });

  const HOURS_MESSAGE = 'Enter your total hours as a whole number.';

  it.each([
    ['', undefined],
    ['0', undefined],
    ['900', undefined],
    ['  900  ', undefined],
    ['99999', undefined],
    ['lots', HOURS_MESSAGE],
    ['-1', HOURS_MESSAGE],
    ['12.5', HOURS_MESSAGE],
    ['1e4', HOURS_MESSAGE],
    ['1,200', HOURS_MESSAGE],
  ])('judges total hours %s', (totalHours, expected) => {
    const values = { ...profileToForm(makeProfile()), total_hours: totalHours };
    expect(validateProfileForm(values).total_hours).toBe(expected);
  });
});
