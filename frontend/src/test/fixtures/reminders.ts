/** Test data for the renewal reminders: the reminder schedule.  Not shipped. */
import type { ReminderSchedule } from '@/portal/api/types';

/** The default schedule (60, 30, 7, 30) that nobody has saved, `overrides` merged over. */
export function makeReminderSchedule(overrides: Partial<ReminderSchedule> = {}): ReminderSchedule {
  return {
    first_days_before: 60,
    second_days_before: 30,
    final_days_before: 7,
    lapsed_days_after: 30,
    updated_by: null,
    updated_at: null,
    ...overrides,
  };
}
