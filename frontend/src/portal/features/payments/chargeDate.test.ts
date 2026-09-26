/** The dates the renewal screens offer, and the day they warn about. */
import { describe, expect, it } from 'vitest';

import { isAfterExpiry, notBeforeToday } from './chargeDate';

describe('notBeforeToday', () => {
  it('keeps a day still to come, which is the day the authority carries', () => {
    expect(notBeforeToday('2027-03-12', new Date(2026, 8, 24))).toBe('2027-03-12');
  });

  it('answers today for a day already gone by, which the box would refuse', () => {
    expect(notBeforeToday('2026-01-31', new Date(2026, 8, 24))).toBe('2026-09-24');
  });

  it('answers today for an authority with no charge waiting at all', () => {
    expect(notBeforeToday(null, new Date(2026, 8, 24))).toBe('2026-09-24');
  });
});

describe('isAfterExpiry', () => {
  it('is true when the charge falls after the membership runs out', () => {
    expect(isAfterExpiry('2027-07-01', '2027-06-30')).toBe(true);
  });

  it('is false on the day the membership runs out, which the charge still covers', () => {
    expect(isAfterExpiry('2027-06-30', '2027-06-30')).toBe(false);
  });

  it('is false for a membership that never runs out', () => {
    expect(isAfterExpiry('2027-07-01', null)).toBe(false);
  });

  it('is false when there is no charge date to compare', () => {
    expect(isAfterExpiry(null, '2027-06-30')).toBe(false);
  });
});
