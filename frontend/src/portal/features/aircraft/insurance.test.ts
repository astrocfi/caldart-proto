import { describe, expect, it } from 'vitest';

import { aircraftExportUrl, aircraftQuery } from './api';
import { aircraftPayload, emptyAircraftValues, validateAircraft } from './form';
import {
  centsToDollars,
  dollarsToCents,
  insuranceTone,
  looksLikeRegistration,
  normalizeNNumber,
} from './insurance';

const TODAY = new Date('2026-06-01T12:00:00');

describe('normalizeNNumber', () => {
  it.each([
    ['12345', 'N12345'],
    ['n12345', 'N12345'],
    ['N-12345', 'N12345'],
    ['  n-172 sp ', 'N172SP'],
    ['737wt', 'N737WT'],
    ['c-gabc', 'CGABC'],
    ['', ''],
    ['---', ''],
  ])('turns %s into %s', (raw, expected) => {
    expect(normalizeNNumber(raw)).toBe(expected);
  });
});

describe('looksLikeRegistration', () => {
  it('needs a digit, so a name is never mistaken for a tail number', () => {
    expect(looksLikeRegistration('N172SP')).toBe(true);
    expect(looksLikeRegistration('172')).toBe(true);
    expect(looksLikeRegistration('Nate')).toBe(false);
  });
});

describe('insuranceTone', () => {
  it('is current when the expiry is comfortably ahead', () => {
    expect(
      insuranceTone({ insurance_is_current: true, insurance_expiration: '2027-01-01' }, TODAY),
    ).toBe('current');
  });

  it('warns inside the 30-day window', () => {
    expect(
      insuranceTone({ insurance_is_current: true, insurance_expiration: '2026-06-20' }, TODAY),
    ).toBe('expiring');
  });

  it('is expired once the date has passed', () => {
    expect(
      insuranceTone({ insurance_is_current: false, insurance_expiration: '2026-05-01' }, TODAY),
    ).toBe('expired');
  });

  it('separates "nothing on file" from "expired"', () => {
    expect(insuranceTone({ insurance_is_current: false, insurance_expiration: null }, TODAY)).toBe(
      'none',
    );
  });
});

describe('money conversion', () => {
  it.each([
    ['1000000', 100_000_000],
    ['$1,000,000', 100_000_000],
    ['123.45', 12_345],
    ['', null],
    ['-5', null],
    ['abc', null],
  ])('reads %s as %s cents', (raw, expected) => {
    expect(dollarsToCents(raw)).toBe(expected);
  });

  it('renders cents back into an editable field', () => {
    expect(centsToDollars(100_000_000)).toBe('1000000');
    expect(centsToDollars(12_345)).toBe('123.45');
    expect(centsToDollars(null)).toBe('');
  });
});

describe('validateAircraft', () => {
  it('requires a registration, a make and a model', () => {
    const errors = validateAircraft(emptyAircraftValues());
    expect(Object.keys(errors).sort()).toEqual(['make', 'model', 'n_number']);
  });

  it('rejects a negative liability limit', () => {
    const values = { ...emptyAircraftValues('N1'), make: 'Cessna', model: '172' };
    values.liability_per_occurrence = '-1';
    expect(validateAircraft(values).liability_per_occurrence).toMatch(/\$0 or more/);
  });

  it('rejects a year that is not four digits', () => {
    const values = { ...emptyAircraftValues('N1'), make: 'Cessna', model: '172', year: '19' };
    expect(validateAircraft(values).year).toMatch(/four-digit/);
  });

  it('accepts a complete record', () => {
    const values = {
      ...emptyAircraftValues('n-172sp'),
      make: 'Cessna',
      model: '172S',
      year: '2008',
      liability_per_occurrence: '1,000,000',
    };
    expect(validateAircraft(values)).toEqual({});
  });
});

describe('aircraftPayload', () => {
  it('normalizes the registration and converts dollars to cents', () => {
    const payload = aircraftPayload({
      ...emptyAircraftValues('n-172sp'),
      make: ' Cessna ',
      model: '172S Skyhawk',
      year: '2008',
      liability_per_occurrence: '1,000,000',
      liability_per_person: '100000',
      hull: '',
      insurance_expiration: '2027-03-01',
    });

    expect(payload).toMatchObject({
      n_number: 'N172SP',
      make: 'Cessna',
      year: 2008,
      insurance_liability_per_occurrence_cents: 100_000_000,
      insurance_liability_per_person_cents: 10_000_000,
      insurance_hull_cents: null,
      insurance_expiration: '2027-03-01',
    });
  });

  it('sends nulls rather than empty strings for the optional numbers', () => {
    const payload = aircraftPayload({ ...emptyAircraftValues('N1'), make: 'C', model: '1' });
    expect(payload.year).toBeNull();
    expect(payload.seats).toBeNull();
    expect(payload.insurance_expiration).toBeNull();
  });
});

describe('query helpers', () => {
  it('drops empty filters', () => {
    expect(aircraftQuery({ search: 'cessna', make: '', insurance: 'current' })).toEqual({
      search: 'cessna',
      insurance: 'current',
    });
  });

  it('builds export URLs that carry the filters but not the page', () => {
    const url = aircraftExportUrl('csv', { search: 'cessna', insurance: 'expired', page: 3 });
    expect(url).toBe('/api/v1/admin/aircraft/export.csv?search=cessna&insurance=expired');
    expect(aircraftExportUrl('pdf', {})).toBe('/api/v1/admin/aircraft/export.pdf');
  });
});
