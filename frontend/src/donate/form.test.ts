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

/** The smallest gift the server takes, in cents, as its config would say. */
const MINIMUM = 500;

describe('validateDonation', () => {
  it('refuses a gift under the smallest the server takes', () => {
    expect(validateDonation(FILLED, 400, MINIMUM).amount).toBe('A donation must be at least $5.');
  });

  it('accepts a gift of the smallest the server takes', () => {
    expect(validateDonation(FILLED, 500, MINIMUM)).toEqual({});
  });

  it('accepts an amount and the three required fields', () => {
    expect(validateDonation(FILLED, 2000, MINIMUM)).toEqual({});
  });

  it('names every missing required field, and never the optional phone', () => {
    expect(Object.keys(validateDonation(EMPTY_DONATION_FORM, 0, MINIMUM))).toEqual([
      'amount',
      'first_name',
      'last_name',
      'email',
    ]);
  });

  it('refuses a phone number that is typed but not ten digits', () => {
    expect(validateDonation({ ...FILLED, phone: '555' }, 2000, MINIMUM).phone).toBe(
      'Use a ten-digit number like 415-555-0100.',
    );
  });

  it('refuses an address that does not read as one', () => {
    expect(validateDonation({ ...FILLED, email: 'pat@example' }, 2000, MINIMUM).email).toBe(
      'Use an email address like name@example.org.',
    );
  });
});

describe('donorBody', () => {
  it('leaves out a phone number nobody typed', () => {
    expect(donorBody({ ...FILLED, phone: '' })).not.toHaveProperty('phone');
  });

  it('sends the required three trimmed, with the phone in its stored form', () => {
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
      volunteer: { ...EMPTY_DONATION_FORM.volunteer, vol_newsletter: true },
    });

    expect(body).toMatchObject({
      city: 'Petaluma',
      state: 'CA',
      pilot_certificate_type: 'private',
      vol_newsletter: true,
    });
  });

  it('leaves out a select left on its default and an unchecked box', () => {
    const body = donorBody(FILLED);

    expect(['pilot_certificate_type', 'vol_newsletter'].some((key) => key in body)).toBe(false);
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
      email: ['Enter a valid email address.'],
      code: 'invalid',
    });

    expect(donorFieldErrors(caught)).toEqual({ email: 'Enter a valid email address.' });
  });

  it('is empty for a refusal that names no form field', () => {
    const caught = new ApiError(400, { detail: 'Nothing to charge.' });

    expect(donorFieldErrors(caught)).toEqual({});
  });

  it('is empty for anything but an ApiError', () => {
    expect(donorFieldErrors(new Error('network down'))).toEqual({});
  });
});
