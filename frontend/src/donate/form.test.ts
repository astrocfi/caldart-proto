import { describe, expect, it } from 'vitest';

import { ApiError } from '@/portal/api/client';
import { EMPTY_DONATION_FORM, donorBody, donorFieldErrors, validateDonation } from './form';
import type { DonationFormValues } from './form';

const FILLED: DonationFormValues = {
  ...EMPTY_DONATION_FORM,
  first_name: ' Pat ',
  last_name: 'Giver',
  email: 'pat@example.org',
  phone: '(415) 555-0100',
};

describe('validateDonation', () => {
  it('accepts an amount and the four required fields', () => {
    expect(validateDonation(FILLED, 2000)).toEqual({});
  });

  it('names every missing required field', () => {
    expect(Object.keys(validateDonation(EMPTY_DONATION_FORM, 0))).toEqual([
      'amount',
      'first_name',
      'last_name',
      'email',
      'phone',
    ]);
  });

  it('refuses an address that does not read as one', () => {
    expect(validateDonation({ ...FILLED, email: 'pat@example' }, 2000).email).toBe(
      'Use an email address like name@example.org.',
    );
  });
});

describe('donorBody', () => {
  it('sends the required four trimmed, with the phone in its stored form', () => {
    expect(donorBody(FILLED)).toEqual({
      first_name: 'Pat',
      last_name: 'Giver',
      email: 'pat@example.org',
      phone: '415-555-0100',
    });
  });

  it('sends an optional field only once it is filled in', () => {
    const body = donorBody({
      ...FILLED,
      city: 'Petaluma',
      state: 'CA',
      pilot_certificate_type: 'private',
      ifr_rated: 'yes',
      volunteer: { ...EMPTY_DONATION_FORM.volunteer, vol_newsletter: true },
    });

    expect(body).toMatchObject({
      city: 'Petaluma',
      state: 'CA',
      pilot_certificate_type: 'private',
      ifr_rated: 'yes',
      vol_newsletter: true,
    });
  });

  it('leaves out a select left on its default and an unticked box', () => {
    const body = donorBody(FILLED);

    expect(
      ['pilot_certificate_type', 'ifr_rated', 'vol_newsletter'].some((key) => key in body),
    ).toBe(false);
  });
});

describe('donorFieldErrors', () => {
  it('reads the message for each form field the server refused', () => {
    const caught = new ApiError(400, {
      email: ['An account already uses that email address. Sign in to donate.'],
      phone: ['Use a ten-digit number.'],
    });

    expect(donorFieldErrors(caught)).toEqual({
      email: 'An account already uses that email address. Sign in to donate.',
      phone: 'Use a ten-digit number.',
    });
  });

  it('leaves out a code the refusal carries alongside a field', () => {
    const caught = new ApiError(400, {
      email: ['An account already uses that email address. Sign in to donate.'],
      code: 'has_account',
    });

    expect(donorFieldErrors(caught)).toEqual({
      email: 'An account already uses that email address. Sign in to donate.',
    });
  });

  it('is empty for a refusal that names no form field', () => {
    const caught = new ApiError(400, { detail: 'Nothing to charge.' });

    expect(donorFieldErrors(caught)).toEqual({});
  });

  it('is empty for anything but an ApiError', () => {
    expect(donorFieldErrors(new Error('network down'))).toEqual({});
  });
});
