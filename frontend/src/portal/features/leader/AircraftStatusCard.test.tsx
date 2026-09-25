import { describe, expect, it } from 'vitest';

import { isInsured } from './AircraftStatusCard';

const TODAY = new Date('2026-09-24T12:00:00Z');

describe('isInsured', () => {
  it.each([
    { tone: 'current', is_current: true, expiration: '2027-03-01', go: true },
    { tone: 'expiring soon', is_current: true, expiration: '2026-10-10', go: true },
    { tone: 'expired', is_current: false, expiration: '2026-01-01', go: false },
    { tone: 'no policy', is_current: false, expiration: null, go: false },
  ])('reads a $tone policy as go=$go', ({ is_current, expiration, go }) => {
    expect(
      isInsured({ insurance_is_current: is_current, insurance_expiration: expiration }, TODAY),
    ).toBe(go);
  });
});
