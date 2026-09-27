import { describe, expect, it } from 'vitest';

import { makeAircraftType } from '@test/fixtures/profile';
import { makeRegistration } from '@test/fixtures/registry';
import { emptyAircraftValues } from './form';
import { ownerTypeForRegistrant, withPickedType, withRegistration } from './registry';

describe('ownerTypeForRegistrant', () => {
  it.each([
    ['individual', 'individual'],
    ['co_owned', 'individual'],
    ['non_citizen_co_owned', 'individual'],
    ['partnership', 'club'],
    ['corporation', 'fbo'],
    ['llc', 'fbo'],
    ['non_citizen_corporation', 'fbo'],
    ['government', null],
    ['unknown', null],
  ] as const)('reads a %s registrant as %s', (registrant, expected) => {
    expect(ownerTypeForRegistrant(registrant)).toBe(expected);
  });
});

describe('withRegistration', () => {
  it('fills the type, year, seats, owner name, and owner type', () => {
    const registration = makeRegistration();
    const filled = withRegistration(emptyAircraftValues('N739TA'), registration);
    expect({
      type: filled.type,
      year: filled.year,
      seats: filled.seats,
      owner_name: filled.owner_name,
      owner_type: filled.owner_type,
    }).toEqual({
      type: registration.type,
      year: '2004',
      seats: '4',
      owner_name: 'PALO ALTO FLYING CLUB',
      owner_type: 'fbo',
    });
  });

  it('leaves what the registry does not say alone', () => {
    const before = {
      ...emptyAircraftValues('N739TA'),
      year: '1999',
      seats: '2',
      owner_type: 'club' as const,
    };
    const filled = withRegistration(
      before,
      makeRegistration({
        year: null,
        registrant_type: 'government',
        type: makeAircraftType({ seats: null }),
      }),
    );
    expect([filled.year, filled.seats, filled.owner_type]).toEqual(['1999', '2', 'club']);
  });

  it('keeps every other field as it was', () => {
    const before = { ...emptyAircraftValues('N739TA'), insurance_carrier: 'Avemco' };
    expect(withRegistration(before, makeRegistration()).insurance_carrier).toBe('Avemco');
  });
});

describe('withPickedType', () => {
  it('fills blank seats from the type', () => {
    const picked = withPickedType(emptyAircraftValues(), makeAircraftType({ seats: 6 }));
    expect(picked.seats).toBe('6');
  });

  it('keeps seats already entered', () => {
    const before = { ...emptyAircraftValues(), seats: '2' };
    expect(withPickedType(before, makeAircraftType({ seats: 6 })).seats).toBe('2');
  });

  it('clears the type without touching the seats', () => {
    const before = { ...emptyAircraftValues(), type: makeAircraftType(), seats: '4' };
    const cleared = withPickedType(before, null);
    expect([cleared.type, cleared.seats]).toEqual([null, '4']);
  });
});
