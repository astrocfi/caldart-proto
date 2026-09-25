import type { JSX } from 'react';

import type { IsoDate } from '@/portal/api/types';

/**
 * Dates read `YYYY/MM/DD` everywhere in the portal, and datetimes add a
 * 24-hour clock. The portal is an administrative screen: a fixed, sortable,
 * unambiguous order beats `Jun 16, 2026`, which reads differently on either
 * side of the Atlantic and lines up in no column.
 */
function pad(value: number): string {
  return String(value).padStart(2, '0');
}

/** Today as `YYYY-MM-DD` on the reader's own clock, for a date box. */
export function todayIso(today: Date = new Date()): IsoDate {
  return `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
}

function dateParts(value: Date): string {
  return `${value.getFullYear()}/${pad(value.getMonth() + 1)}/${pad(value.getDate())}`;
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

/** Formats an ISO date or datetime as a short date, or `placeholder` when it is unparseable. */
export function formatDate(iso: string | null | undefined, placeholder = '—'): string {
  if (!iso) return placeholder;
  const value = parse(iso);
  return value ? dateParts(value) : placeholder;
}

/** Formats an ISO datetime with the time of day, or `placeholder` when it is unparseable. */
export function formatDateTime(iso: string | null | undefined, placeholder = '—'): string {
  if (!iso) return placeholder;
  const value = parse(iso);
  return value ? `${dateParts(value)} ${timeParts(value)}` : placeholder;
}

export interface DateTextProps {
  value: string | null | undefined;
  /** Include the time of day. */
  withTime?: boolean;
  placeholder?: string;
}

/** Dates render in the mono face so columns line up. */
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
