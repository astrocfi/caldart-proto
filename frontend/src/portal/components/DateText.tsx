import type { JSX } from 'react';

const DATE_FORMAT = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
});

const DATETIME_FORMAT = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
});

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
  return value ? DATE_FORMAT.format(value) : placeholder;
}

/** Formats an ISO datetime with the time of day, or `placeholder` when it is unparseable. */
export function formatDateTime(iso: string | null | undefined, placeholder = '—'): string {
  if (!iso) return placeholder;
  const value = parse(iso);
  return value ? DATETIME_FORMAT.format(value) : placeholder;
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
