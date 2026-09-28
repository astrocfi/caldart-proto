/**
 * The one place the portal turns a date or a time into text.
 *
 * Every date or time a portal screen shows passes through this module, so the
 * format can change here alone: dates read `MM/DD/YYYY`, datetimes add a
 * 24-hour `HH:MM`, a time of day alone reads `HH:MM`, and a month reads
 * `Mar 2026`. Date inputs stay native `<input type="date">`, which the browser
 * renders in the reader's own locale; `todayIso` gives them their value.
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

function timeParts(value: Date): string {
  return `${pad(value.getHours())}:${pad(value.getMinutes())}`;
}

function parse(iso: string): Date | null {
  // A bare `YYYY-MM-DD` parses as UTC midnight, which reads as the previous
  // day west of Greenwich; pin it to local midnight instead.
  const value = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? new Date(`${iso}T00:00:00`) : new Date(iso);
  return Number.isNaN(value.getTime()) ? null : value;
}

/** Formats an ISO date or datetime as `MM/DD/YYYY`, or `placeholder` when it is unparseable. */
export function formatDate(iso: string | null | undefined, placeholder = '—'): string {
  if (!iso) return placeholder;
  const value = parse(iso);
  return value ? dateParts(value) : placeholder;
}

/** Formats an ISO datetime as `MM/DD/YYYY HH:MM`, or `placeholder` when it is unparseable. */
export function formatDateTime(iso: string | null | undefined, placeholder = '—'): string {
  if (!iso) return placeholder;
  const value = parse(iso);
  return value ? `${dateParts(value)} ${timeParts(value)}` : placeholder;
}

/** Formats an ISO datetime's time of day as `HH:MM`, or `placeholder` when it is unparseable. */
export function formatTime(iso: string | null | undefined, placeholder = '—'): string {
  if (!iso) return placeholder;
  const value = parse(iso);
  return value ? timeParts(value) : placeholder;
}

/** Formats a `YYYY-MM` month as `Mar 2026`; any other value comes back unchanged. */
export function formatMonth(yyyyMm: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(yyyyMm);
  const month = match ? MONTH_ABBREVIATIONS[Number(match[2]) - 1] : undefined;
  return match && month ? `${month} ${match[1]}` : yyyyMm;
}

export interface DateTextProps {
  value: string | null | undefined;
  /** Include the time of day. */
  withTime?: boolean;
  placeholder?: string;
}

/** A date, or a datetime with `withTime`, in the mono face so columns line up. */
export function DateText({
  value,
  withTime = false,
  placeholder = '—',
}: DateTextProps): JSX.Element {
  if (!value) return <span className="mono muted">{placeholder}</span>;
  const parsed = parse(value);
  const text = withTime ? formatDateTime(value, placeholder) : formatDate(value, placeholder);
  return (
    <time className="mono" dateTime={parsed ? value : undefined}>
      {text}
    </time>
  );
}
