import { describe, expect, it } from 'vitest';

import { NOT_VERIFIED, VERIFIED } from '@test/handlers';
import { aircraftVerdict, insuranceVerdict, isInsured } from './AircraftStatusCard';

const TODAY = new Date('2026-09-24T12:00:00Z');

describe('isInsured', () => {
  it.each([
    { tone: 'current', is_current: true, expiration: '2027-03-01', go: true },
    { tone: 'expiring soon', is_current: true, expiration: '2026-10-10', go: true },
    { tone: 'expired', is_current: false, expiration: '2026-01-01', go: false },
    { tone: 'no policy', is_current: false, expiration: null, go: false },
  ])('reads a verified $tone policy as go=$go', ({ is_current, expiration, go }) => {
    expect(
      isInsured(
        {
          insurance_is_current: is_current,
          insurance_expiration: expiration,
          insurance_verification: VERIFIED,
        },
        TODAY,
      ),
    ).toBe(go);
  });

  it('reads a current policy nobody has verified as no go', () => {
    expect(
      isInsured(
        {
          insurance_is_current: true,
          insurance_expiration: '2027-03-01',
          insurance_verification: NOT_VERIFIED,
        },
        TODAY,
      ),
    ).toBe(false);
  });
});

describe('insuranceVerdict', () => {
  it.each([
    {
      state: 'current and verified',
      current: true,
      verified: true,
      word: 'INSURED',
      mark: 'Insured',
    },
    {
      state: 'current, not verified',
      current: true,
      verified: false,
      word: 'NOT VERIFIED',
      mark: 'Not verified',
    },
    {
      state: 'lapsed, verified',
      current: false,
      verified: true,
      word: 'NOT INSURED',
      mark: 'Not insured',
    },
    {
      state: 'lapsed, not verified',
      current: false,
      verified: false,
      word: 'NOT INSURED',
      mark: 'Not insured',
    },
  ])('reads a $state policy as $word', ({ current, verified, word, mark }) => {
    const verdict = insuranceVerdict(
      {
        insurance_is_current: current,
        insurance_expiration: current ? '2027-03-01' : '2026-01-01',
        insurance_verification: verified ? VERIFIED : NOT_VERIFIED,
      },
      TODAY,
    );
    expect({ word: verdict.word, mark: verdict.mark }).toEqual({ word, mark });
  });
});

describe('aircraftVerdict', () => {
  const insured = {
    insurance_is_current: true,
    insurance_expiration: '2027-03-01',
    insurance_verification: VERIFIED,
  };

  it('reads an aircraft the policy excludes as NOT COVERED, with the reason', () => {
    const reason = "Not covered: helicopters are excluded by CalDART's policy";
    const verdict = aircraftVerdict({ ...insured, coverage: { excluded: true, reason } }, TODAY);
    expect(verdict).toEqual({
      word: 'NOT COVERED',
      why: "helicopters are excluded by CalDART's policy",
      mark: 'Not covered',
      go: false,
    });
  });

  it('reads a covered aircraft by its insurance', () => {
    const verdict = aircraftVerdict(
      { ...insured, coverage: { excluded: false, reason: 'Category not recorded' } },
      TODAY,
    );
    expect(verdict.word).toBe('INSURED');
  });
});
