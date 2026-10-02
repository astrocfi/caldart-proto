/**
 * The words the reminder screens print for the reminder stages, built from the stored
 * reminder schedule so they name the days the scan actually uses.
 */
import type { ReminderKind, ReminderSchedulePayload } from '@/portal/api/types';

/** The five stages, in the order a term reaches them. */
export const REMINDER_KINDS: readonly ReminderKind[] = [
  'first',
  'second',
  'final',
  'expired',
  'lapsed',
];

/** What each stage is called before the schedule that dates it has loaded. */
const KIND_NAMES: Record<ReminderKind, string> = {
  first: 'First reminder',
  second: 'Second reminder',
  final: 'Final reminder',
  expired: 'Expired',
  lapsed: 'Lapsed',
};

/** One of the schedule's day fields: its name, its label, and which side of expiry it counts. */
export interface ScheduleField {
  name: keyof ReminderSchedulePayload;
  label: string;
  side: 'before' | 'after';
}

/** The schedule's four day fields, in the order a term reaches them. */
export const SCHEDULE_FIELDS: readonly ScheduleField[] = [
  { name: 'first_days_before', label: 'First reminder', side: 'before' },
  { name: 'second_days_before', label: 'Second reminder', side: 'before' },
  { name: 'final_days_before', label: 'Final reminder', side: 'before' },
  { name: 'lapsed_days_after', label: 'Lapsed reminder', side: 'after' },
];

/** `count` with "day" or "days". */
export function days(count: number): string {
  return count === 1 ? '1 day' : `${count} days`;
}

/**
 * Each stage in words, such as "60 days before", "Expired", and "30 days after".
 *
 * @param schedule the stored schedule, or `undefined` while it loads, when each stage
 *   reads by its name ("First reminder") instead.
 */
export function kindLabels(
  schedule: ReminderSchedulePayload | undefined,
): Record<ReminderKind, string> {
  if (schedule === undefined) return KIND_NAMES;
  return {
    first: `${days(schedule.first_days_before)} before`,
    second: `${days(schedule.second_days_before)} before`,
    final: `${days(schedule.final_days_before)} before`,
    expired: 'Expired',
    lapsed: `${days(schedule.lapsed_days_after)} after`,
  };
}

/**
 * The whole schedule as one phrase: "60, 30, and 7 days before, on the day, and 30 days
 * after" on the defaults.
 */
export function schedulePhrase(schedule: ReminderSchedulePayload): string {
  const { first_days_before: first, second_days_before: second } = schedule;
  return (
    `${first}, ${second}, and ${days(schedule.final_days_before)} before, on the day, ` +
    `and ${days(schedule.lapsed_days_after)} after`
  );
}
