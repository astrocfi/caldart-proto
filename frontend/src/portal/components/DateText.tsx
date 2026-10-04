/**
 * The one place the portal turns a date or a time into text.
 *
 * Every date or time a portal screen shows passes through this module, so the
 * format can change here alone.  A date reads `MM/DD/YYYY`; a moment reads
 * `10/04/2026 at 5:33 AM`, always in the site's own time zone (Pacific), whoever is
 * reading and wherever they are, so the same moment reads the same on every screen;
 * a time of day alone reads `5:33 AM`; and a month reads `Mar 2026`.  A moment shown
 * as a date alone is its Pacific day.  Date inputs stay native
 * `<input type="date">`, which the browser renders in the reader's own locale;
 * `todayIso` gives them their value.
 */
import type { JSX } from 'react';

import type { IsoDate } from '@/portal/api/types';

/** Three-letter month names, so no month label wraps in a narrow column. */
const MONTH_ABBREVIATIONS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
] as const;

function pad(value: number): string {
  return String(value).padStart(2, '0');
}

/** Today as `YYYY-MM-DD` on the reader's own clock, for a date box. */
export function todayIso(today: Date = new Date()): IsoDate {
  return `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
}

function dateParts(value: Date): string {
  return `${pad(value.getMonth() + 1)}/${pad(value.getDate())}/${value.getFullYear()}`;
}

/** The site's time zone, in which every moment is read and every schedule is chosen. */
export const SITE_TIME_ZONE = 'America/Los_Angeles';

/** What the site's time zone is called on screen. */
export const SITE_TIME_ZONE_NAME = 'Pacific time';

const BARE_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** The named parts of `value` in `timeZone` (the reader's own zone when undefined). */
function zonedParts(
  value: Date,
  timeZone: string | undefined,
): (type: Intl.DateTimeFormatPartTypes) => string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).formatToParts(value);
  return (type) => parts.find((piece) => piece.type === type)?.value ?? '';
}

function parse(iso: string): Date | null {
  // A bare `YYYY-MM-DD` parses as UTC midnight, which reads as the previous
  // day west of Greenwich; pin it to local midnight instead.
  const value = BARE_DATE.test(iso) ? new Date(`${iso}T00:00:00`) : new Date(iso);
  return Number.isNaN(value.getTime()) ? null : value;
}

/**
 * Formats an ISO date as `MM/DD/YYYY`, that day wherever the reader is, or an ISO
 * datetime as the Pacific day it falls on; `placeholder` when it is unparseable.
 */
export function formatDate(iso: string | null | undefined, placeholder = '—'): string {
  if (!iso) return placeholder;
  const value = parse(iso);
  if (value === null) return placeholder;
  if (BARE_DATE.test(iso)) return dateParts(value);
  const part = zonedParts(value, SITE_TIME_ZONE);
  return `${part('month')}/${part('day')}/${part('year')}`;
}

/**
 * Formats an ISO datetime as `10/04/2026 at 5:33 AM` in Pacific time, or
 * `placeholder` when it is unparseable: `formatDateAt` in the site's time zone.
 */
export function formatDateTime(iso: string | null | undefined, placeholder = '—'): string {
  return formatDateAt(iso, SITE_TIME_ZONE, placeholder);
}

/**
 * Formats an ISO datetime's time of day as `5:33 AM` in Pacific time, or `placeholder`
 * when it is unparseable.
 */
export function formatTime(iso: string | null | undefined, placeholder = '—'): string {
  if (!iso) return placeholder;
  const value = parse(iso);
  if (value === null) return placeholder;
  const part = zonedParts(value, SITE_TIME_ZONE);
  return `${part('hour')}:${part('minute')} ${part('dayPeriod')}`;
}

/**
 * Formats a datetime as `04/07/2026 at 8:00 AM`, in `timeZone` when one is given and
 * on the reader's own clock otherwise, or `placeholder` when it is unparseable.  A
 * moment the server holds is read in `SITE_TIME_ZONE` (`formatDateTime`); the reader's
 * own clock is for a time they have chosen in the boxes and not yet saved.
 */
export function formatDateAt(
  iso: string | null | undefined,
  timeZone?: string,
  placeholder = '—',
): string {
  if (!iso) return placeholder;
  const value = parse(iso);
  if (value === null) return placeholder;
  const part = zonedParts(value, timeZone);
  return `${part('month')}/${part('day')}/${part('year')} at ${part('hour')}:${part('minute')} ${part('dayPeriod')}`;
}

/**
 * The `YYYY-MM-DD` date and the `HH:MM` 24-hour time a moment falls on in
 * `timeZone`, for a date box and a time box to start from.
 */
export function datePartsIn(iso: string, timeZone: string): { date: string; time: string } {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(iso));
  const part = (type: Intl.DateTimeFormatPartTypes): string =>
    parts.find((piece) => piece.type === type)?.value ?? '';
  return {
    date: `${part('year')}-${part('month')}-${part('day')}`,
    time: `${part('hour')}:${part('minute')}`,
  };
}

/** Formats a `YYYY-MM` month as `Mar 2026`; any other value comes back unchanged. */
export function formatMonth(yyyyMm: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(yyyyMm);
  const month = match ? MONTH_ABBREVIATIONS[Number(match[2]) - 1] : undefined;
  return match && month ? `${month} ${match[1]}` : yyyyMm;
}

export interface DateTextProps {
  value: string | null | undefined;
  /** Include the time of day: `10/04/2026 at 5:33 AM`, in Pacific time. */
  withTime?: boolean;
  placeholder?: string;
}

/**
 * A date, or a moment with `withTime`, in a `time` element, with tabular digits so
 * a column of them lines up.
 */
export function DateText({
  value,
  withTime = false,
  placeholder = '—',
}: DateTextProps): JSX.Element {
  if (!value) return <span className="num muted">{placeholder}</span>;
  const parsed = parse(value);
  const text = withTime ? formatDateTime(value, placeholder) : formatDate(value, placeholder);
  return (
    <time className="num" dateTime={parsed ? value : undefined}>
      {text}
    </time>
  );
}
