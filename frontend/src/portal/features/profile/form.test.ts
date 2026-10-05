import { describe, expect, it } from 'vitest';

import { makeProfile } from '@test/fixtures/profile';
import { makeVerifiedProfile } from '@test/handlers';
import {
  EMPTY_PROFILE_FORM,
  REQUIRED_PROFILE_FIELDS,
  formToMemberPatch,
  formToPatch,
  maskCallsign,
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

  it('reads the kind of photo ID onto its select', () => {
    expect(profileToForm(makeVerifiedProfile({ photo_id_type: 'passport' })).photo_id_type).toBe(
      'passport',
    );
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

  it('sends the kind of photo ID', () => {
    const patch = formToPatch({ ...EMPTY_PROFILE_FORM, photo_id_type: 'military_id' });
    expect(patch.photo_id_type).toBe('military_id');
  });

  it('starts a blank form on no photo ID provided', () => {
    expect(EMPTY_PROFILE_FORM.photo_id_type).toBe('not_provided');
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

  it('sends the secondary airport upper-cased and trimmed', () => {
    const patch = formToPatch({ ...EMPTY_PROFILE_FORM, secondary_airport_identifier: ' sql ' });
    expect(patch.secondary_airport_identifier).toBe('SQL');
  });

  it.each(['home_airport_city', 'ifr_rated'])('sends no %s', (field) => {
    expect(field in formToPatch(EMPTY_PROFILE_FORM)).toBe(false);
  });
});

describe('formToMemberPatch', () => {
  it('adds the trimmed names when the form shows them', () => {
    const values = { ...profileToForm(makeProfile()), first_name: ' Ann ', last_name: 'Lee ' };
    expect(formToMemberPatch(values, true)).toMatchObject({ first_name: 'Ann', last_name: 'Lee' });
  });

  it('leaves the names out when the form does not show them', () => {
    expect(formToMemberPatch(profileToForm(makeProfile()), false)).not.toHaveProperty('first_name');
  });
});

describe('formToPatch names and callsign', () => {
  it('never sends the names, which the member record writes on the account', () => {
    expect(formToPatch(profileToForm(makeProfile()))).not.toHaveProperty('last_name');
  });

  it('sends the callsign upper case without spaces', () => {
    const patch = formToPatch({ ...EMPTY_PROFILE_FORM, ham_callsign: 'w6 abc' });
    expect(patch.ham_callsign).toBe('W6ABC');
  });
});

describe('profileToForm names', () => {
  it('reads the names off the member’s own profile', () => {
    const values = profileToForm(makeProfile({ first_name: 'Ann', last_name: 'Lee' }));
    expect([values.first_name, values.last_name]).toEqual(['Ann', 'Lee']);
  });

  it('reads absent names as blank, as the member record’s profile has none', () => {
    const { first_name: _first, last_name: _last, ...rest } = makeProfile();
    expect(profileToForm(rest).first_name).toBe('');
  });
});

describe('maskCallsign', () => {
  it.each([
    ['w6abc', 'W6ABC'],
    ['w6 a-b.c', 'W6ABC'],
    ['WA6ABCD', 'WA6ABC'],
    ['', ''],
  ])('turns %j into %j', (typed, kept) => {
    expect(maskCallsign(typed)).toBe(kept);
  });
});

describe('validateProfileForm', () => {
  it.each(['home_airport_identifier', 'secondary_airport_identifier'] as const)(
    'refuses a %s that is not three letters or digits',
    (field) => {
      const errors = validateProfileForm({ ...EMPTY_PROFILE_FORM, [field]: 'PA' });
      expect(errors[field]).toBe('Use a three-character identifier like PAO, E16, or KLS.');
    },
  );

  it('accepts a filled-in profile', () => {
    expect(validateProfileForm(profileToForm(makeProfile()))).toEqual({});
  });

  it('lists the same fields the server calls a complete profile', () => {
    expect([...REQUIRED_PROFILE_FIELDS].sort()).toEqual([
      'address_line1',
      'city',
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
      address_line1: 'Enter your street address.',
      city: 'Enter your city.',
      postal_code: 'Enter your ZIP code.',
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

  const POSTAL_MESSAGE = 'Use a 5-digit ZIP code, such as 95035.';

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

  it.each(['W6ABC', 'K6A', 'KD6AB', 'AA6A', 'AL7XYZ', ''])('accepts the callsign %j', (call) => {
    expect(
      validateProfileForm({ ...profileToForm(makeProfile()), ham_callsign: call }).ham_callsign,
    ).toBeUndefined();
  });

  it.each(['X1ABC', 'AM6ABC', 'W6', 'W6A1', 'WAB6ABC'])('refuses the callsign %j', (call) => {
    expect(
      validateProfileForm({ ...profileToForm(makeProfile()), ham_callsign: call }).ham_callsign,
    ).toBe('Enter a US amateur radio callsign, such as W6ABC.');
  });

  it('wants both names when the form shows them', () => {
    const errors = validateProfileForm(
      { ...profileToForm(makeProfile()), first_name: ' ', last_name: '' },
      true,
    );
    expect([errors.first_name, errors.last_name]).toEqual([
      'Enter your first name.',
      'Enter your last name.',
    ]);
  });

  it('asks nothing of the names when the form does not show them', () => {
    expect(
      validateProfileForm({ ...profileToForm(makeProfile()), first_name: '' }).first_name,
    ).toBeUndefined();
  });

  it('leaves the medical expiration optional when a medical is claimed', () => {
    const values = { ...profileToForm(makeProfile()), medical_expiration: '' };
    expect(validateProfileForm(values).medical_expiration).toBeUndefined();
  });

  it('leaves the certificate number optional when a certificate is claimed', () => {
    const values = { ...profileToForm(makeProfile()), certificate_number: '  ' };
    expect(validateProfileForm(values).certificate_number).toBeUndefined();
  });

  it('refuses a certificate number short of seven digits', () => {
    const values = { ...profileToForm(makeProfile()), certificate_number: '12345' };
    expect(validateProfileForm(values).certificate_number).toBe(
      'Enter the 7 digits of the pilot certificate number.',
    );
  });

  it('accepts a seven-digit certificate number', () => {
    const values = { ...profileToForm(makeProfile()), certificate_number: '0123456' };
    expect(validateProfileForm(values).certificate_number).toBeUndefined();
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
