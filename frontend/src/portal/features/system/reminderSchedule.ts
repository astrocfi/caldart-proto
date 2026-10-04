/**
 * The words the reminder screens print for the reminder stages, built from the stored
 * reminder schedule so they name the days the nightly check actually uses.
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

/** Each stage's one name, used on every screen that lists reminders. */
const STAGE_NAMES: Record<ReminderKind, string> = {
  first: 'First reminder',
  second: 'Second reminder',
  final: 'Final reminder',
  expired: 'Expired reminder',
  lapsed: 'Lapsed reminder',
};

/**
 * One of the schedule's day fields: its name, its label, which side of expiry it counts,
 * and the outer bounds the server holds it to.
 */
export interface ScheduleField {
  name: keyof ReminderSchedulePayload;
  label: string;
  side: 'before' | 'after';
  min: number;
  max: number;
}

/** The schedule's four day fields, in the order a term reaches them. */
export const SCHEDULE_FIELDS: readonly ScheduleField[] = [
  { name: 'first_days_before', label: 'First reminder', side: 'before', min: 1, max: 180 },
  { name: 'second_days_before', label: 'Second reminder', side: 'before', min: 1, max: 180 },
  { name: 'final_days_before', label: 'Final reminder', side: 'before', min: 1, max: 180 },
  { name: 'lapsed_days_after', label: 'Lapsed reminder', side: 'after', min: 7, max: 365 },
];

/** `count` with "day" or "days". */
export function days(count: number): string {
  return count === 1 ? '1 day' : `${count} days`;
}

/**
 * Each stage by its one name, with its day once the schedule has loaded, such as
 * "First reminder (60 days before)", "Expired reminder (up to 6 days after)", and "Lapsed
 * reminder (30 days after)".
 *
 * @param schedule the stored schedule, or `undefined` while it loads, when each stage
 *   reads by its name alone ("First reminder").
 */
export function kindLabels(
  schedule: ReminderSchedulePayload | undefined,
): Record<ReminderKind, string> {
  if (schedule === undefined) return STAGE_NAMES;
  return {
    first: `${STAGE_NAMES.first} (${days(schedule.first_days_before)} before)`,
    second: `${STAGE_NAMES.second} (${days(schedule.second_days_before)} before)`,
    final: `${STAGE_NAMES.final} (${days(schedule.final_days_before)} before)`,
    expired: `${STAGE_NAMES.expired} (up to 6 days after)`,
    lapsed: `${STAGE_NAMES.lapsed} (${days(schedule.lapsed_days_after)} after)`,
  };
}

/** How a schedule phrase names the days before expiry, and the day itself. */
export interface PhraseWording {
  /** Follows the three counts before expiry, such as "before". */
  before: string;
  /** Names the expiry day, such as "on the day". */
  onTheDay: string;
}

const DEFAULT_WORDING: PhraseWording = { before: 'before', onTheDay: 'on the day' };

/**
 * The whole schedule as one phrase: "60, 30, and 7 days before, on the day, and 30 days
 * after" on the defaults.
 *
 * @param wording replaces "before" and "on the day", such as "before their membership
 *   ends" and "on the day it ends".
 */
export function schedulePhrase(
  schedule: ReminderSchedulePayload,
  wording: PhraseWording = DEFAULT_WORDING,
): string {
  const { first_days_before: first, second_days_before: second } = schedule;
  return (
    `${first}, ${second}, and ${days(schedule.final_days_before)} ${wording.before}, ` +
    `${wording.onTheDay}, and ${days(schedule.lapsed_days_after)} after`
  );
}
