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

  it('defaults a missing state to CA', () => {
    expect(profileToForm(makeProfile({ state: 'CA' })).state).toBe('CA');
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

  it('nulls the empty date, hour, and dart values', () => {
    const patch = formToPatch({ ...EMPTY_PROFILE_FORM, phone: '415-555-0100' });
    expect(patch.dart_id).toBeNull();
    expect(patch.medical_expiration).toBeNull();
    expect(patch.flight_review_date).toBeNull();
    expect(patch.total_hours).toBeNull();
  });

  it('sends every phone in the one stored shape', () => {
    const patch = formToPatch({
      ...EMPTY_PROFILE_FORM,
      phone: '  +1 (415) 555.0100  ',
      phone_alt: '4155550199',
      emergency_contact_phone: '1-415-555-0111',
      home_airport_identifier: 'pao',
    });
    expect(patch.phone).toBe('415-555-0100');
    expect(patch.phone_alt).toBe('415-555-0199');
    expect(patch.emergency_contact_phone).toBe('415-555-0111');
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
      'state',
    ]);
  });

  // `pilot_certificate_type` is required too, but it is a select that always
  // holds a value, so it cannot be missing from a rendered form.
  it('names every missing required field in its own words', () => {
    const errors = validateProfileForm({ ...EMPTY_PROFILE_FORM, postal_code: '' });
    expect(errors).toEqual({
      phone: 'A phone number is required.',
      address_line1: 'Your street address is required.',
      city: 'Your city is required.',
      postal_code: 'Your ZIP code is required.',
    });
  });

  const PHONE_MESSAGE = 'Use a ten-digit number like 415-555-0100.';

  it.each([
    ['415-555-0100', undefined],
    ['(415) 555-0100', undefined],
    ['+1 415 555 0100', undefined],
    ['4155550100', undefined],
    ['555-0100', PHONE_MESSAGE],
    ['415-555-010', PHONE_MESSAGE],
    ['415-555-01000', PHONE_MESSAGE],
    ['call the office', PHONE_MESSAGE],
  ])('judges the phone number %s', (phone, expected) => {
    expect(validateProfileForm({ ...EMPTY_PROFILE_FORM, phone }).phone).toBe(expected);
  });

  it('judges the alternate and emergency numbers the same way', () => {
    const errors = validateProfileForm({
      ...EMPTY_PROFILE_FORM,
      phone: '415-555-0100',
      phone_alt: '12345',
      emergency_contact_phone: '415 555 0111',
    });
    expect(errors.phone_alt).toBe(PHONE_MESSAGE);
    expect(errors.emergency_contact_phone).toBeUndefined();
  });

  it('takes an extension of digits only', () => {
    const values = { ...EMPTY_PROFILE_FORM, phone: '415-555-0100' };
    expect(validateProfileForm({ ...values, phone_extension: '4021' }).phone_extension).toBe(
      undefined,
    );
    expect(validateProfileForm({ ...values, phone_extension: 'x40' }).phone_extension).toBe(
      'An extension is digits only, for example 4021.',
    );
  });

  const POSTAL_MESSAGE = 'Use a five-digit ZIP code like 95035.';

  it.each([
    ['94559', undefined],
    ['9455', POSTAL_MESSAGE],
    ['945590', POSTAL_MESSAGE],
    ['94559-1234', POSTAL_MESSAGE],
    ['94559 1234', POSTAL_MESSAGE],
    ['SW1A 1AA', POSTAL_MESSAGE],
  ])('judges the ZIP code %s', (postalCode, expected) => {
    const values = {
      ...EMPTY_PROFILE_FORM,
      phone: '415-555-0100',
      city: 'Napa',
      postal_code: postalCode,
    };
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
