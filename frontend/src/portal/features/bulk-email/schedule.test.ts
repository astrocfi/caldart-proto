import { describe, expect, it } from 'vitest';

import { chosenWords, scheduledWords, sitePartsOf, TIME_CHOICES, timeChoice } from './schedule';

describe('the schedule words', () => {
  it('reads a stored start in Pacific time with a twelve-hour clock', () => {
    expect(scheduledWords('2026-10-04T15:00:00Z')).toBe('10/04/2026 at 8:00 AM Pacific time');
  });

  it('reads a chosen time the same way', () => {
    expect(chosenWords('2026-10-04T08:00')).toBe('10/04/2026 at 8:00 AM Pacific time');
  });

  it('finds the boxes a stored start falls in', () => {
    expect(sitePartsOf('2026-10-04T15:00:00Z')).toEqual({ date: '2026-10-04', time: '08:00' });
  });
});

describe('the time box', () => {
  it('offers every half hour, from midnight', () => {
    expect([TIME_CHOICES.length, TIME_CHOICES[0]?.label, TIME_CHOICES[17]?.label]).toEqual([
      48,
      '12:00 AM',
      '8:30 AM',
    ]);
  });

  it('reads an afternoon time with PM', () => {
    expect(timeChoice('13:45')).toEqual({ value: '13:45', label: '1:45 PM' });
  });
});
