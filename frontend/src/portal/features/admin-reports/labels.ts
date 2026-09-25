/**
 * The words the reports screens put to what the server sends: a
 * subscription's schedule and recipient, and what a run of the report sender
 * did.
 */
import type { ReportCadence, ReportFormats, ReportSubscription } from '@/portal/api/types';
import type { Option } from '@/portal/reports/types';
import { skippedBreakdown } from '@/portal/components/runSummary';

/** The weekdays as `weekday` counts them: 0 is Monday, 6 is Sunday. */
export const WEEKDAY_NAMES: readonly string[] = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
];

/** Each cadence as a schedule reads it, and in the order the form offers them. */
export const CADENCE_LABELS: Record<ReportCadence, string> = {
  weekly: 'Weekly',
  monthly: 'Monthly',
  quarterly: 'Quarterly',
  yearly: 'Yearly',
};

/** Which files a subscription attaches, in the order the form offers them. */
export const FORMAT_LABELS: Record<ReportFormats, string> = {
  csv: 'CSV',
  pdf: 'PDF',
  both: 'Both',
};

/** The weekday choices of a weekly schedule, Monday first. */
export const WEEKDAY_OPTIONS: readonly Option[] = WEEKDAY_NAMES.map((name, day) => ({
  value: String(day),
  label: name,
}));

/**
 * Why the report sender passed a subscription or a person over, in words.
 *
 * `not_permitted`: the account no longer holds a role that may read the report
 * (the subscription is paused); `no_recipients`: a DART has nobody ticked with
 * an address; `no_email`: a ticked person has no address.
 */
const REPORT_SKIPPED_REASON_LABELS: Record<string, string> = {
  not_permitted: 'no longer permitted',
  no_recipients: 'nobody ticked',
  no_email: 'no address on file',
};

/** What each kind of email the report sender sends reads as in the actions table. */
const REPORT_KIND_LABELS: Record<string, string> = {
  report: 'Report',
  roster: 'Roster',
};

/**
 * How a subscription's schedule reads in the table.
 *
 * @param cadence how often it is sent.
 * @param weekday 0 (Monday) to 6 (Sunday), read by `weekly` alone.
 * @returns `Weekly on Monday`, `Monthly`, `Quarterly` or `Yearly`.
 */
export function scheduleLabel(cadence: ReportCadence, weekday: number): string {
  if (cadence !== 'weekly') return CADENCE_LABELS[cadence];
  return `${CADENCE_LABELS.weekly} on ${WEEKDAY_NAMES[weekday] ?? WEEKDAY_NAMES[0]}`;
}

/**
 * Who a subscription goes to: the account's name, or the bare address for
 * somebody outside CalDART.
 */
export function recipientLabel(subscription: ReportSubscription): string {
  return subscription.recipient_name === ''
    ? subscription.recipient_email
    : subscription.recipient_name;
}

/** A report run's action kind in words, or its slug when it names no kind above. */
export function reportKindLabel(kind: string): string {
  return REPORT_KIND_LABELS[kind] ?? kind;
}

/** `Skipped: <reason> <count>, …` for a run of the report sender, or `''`. */
export function reportSkippedBreakdown(byReason: Record<string, number>): string {
  return skippedBreakdown(byReason, REPORT_SKIPPED_REASON_LABELS);
}
