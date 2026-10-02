import { describe, expect, it } from 'vitest';

import { makeReminderSchedule } from '@test/fixtures/reminders';
import { days, kindLabels, schedulePhrase } from './reminderSchedule';

describe('kindLabels', () => {
  it('names every stage by the days of the schedule', () => {
    expect(kindLabels(makeReminderSchedule())).toEqual({
      first: '60 days before',
      second: '30 days before',
      final: '7 days before',
      expired: 'Expired',
      lapsed: '30 days after',
    });
  });

  it('names every stage by its name while the schedule loads', () => {
    expect(kindLabels(undefined)).toEqual({
      first: 'First reminder',
      second: 'Second reminder',
      final: 'Final reminder',
      expired: 'Expired',
      lapsed: 'Lapsed',
    });
  });

  it('reads a final reminder one day out in the singular', () => {
    expect(kindLabels(makeReminderSchedule({ final_days_before: 1 })).final).toBe('1 day before');
  });
});

describe('schedulePhrase', () => {
  it('reads the whole schedule as one phrase', () => {
    expect(schedulePhrase(makeReminderSchedule({ first_days_before: 90 }))).toBe(
      '90, 30, and 7 days before, on the day, and 30 days after',
    );
  });
});

describe('days', () => {
  it.each([
    [1, '1 day'],
    [2, '2 days'],
  ])('reads %i as "%s"', (count, expected) => {
    expect(days(count)).toBe(expected);
  });
});
