/** The date helpers every screen that reads or offers a date shares. */
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@test/render';

import {
  DateText,
  formatDate,
  formatDateAt,
  formatDateTime,
  formatMonth,
  formatTime,
  todayIso,
} from './DateText';

describe('todayIso', () => {
  it('writes the reader’s own day as the date box wants it', () => {
    expect(todayIso(new Date(2026, 8, 4))).toBe('2026-09-04');
  });
});

describe('formatDate', () => {
  it('reads a bare ISO date as MM/DD/YYYY with leading zeros', () => {
    expect(formatDate('2026-09-04')).toBe('09/04/2026');
  });

  it('reads a bare ISO date as that day wherever the reader is', () => {
    expect(formatDate('2027-01-01')).toBe('01/01/2027');
  });

  it('reads a datetime as its Pacific day', () => {
    expect(formatDate('2026-03-08T07:59:00Z')).toBe('03/07/2026');
  });

  it('reads a datetime after Pacific midnight as the next day', () => {
    expect(formatDate('2026-03-08T08:01:00Z')).toBe('03/08/2026');
  });

  it('gives the placeholder for a missing value', () => {
    expect(formatDate(null)).toBe('—');
  });

  it('gives the placeholder for an unparseable value', () => {
    expect(formatDate('not a date', 'Never')).toBe('Never');
  });
});

describe('formatDateTime', () => {
  it('reads a moment in Pacific time on the 12-hour clock, whatever the reader’s zone', () => {
    expect(formatDateTime('2026-10-04T12:33:00Z')).toBe('10/04/2026 at 5:33 AM');
  });

  it('reads an afternoon moment with PM', () => {
    expect(formatDateTime('2026-09-27T21:05:00Z')).toBe('09/27/2026 at 2:05 PM');
  });

  it('reads midnight Pacific as 12:00 AM', () => {
    expect(formatDateTime('2026-01-15T08:00:00Z')).toBe('01/15/2026 at 12:00 AM');
  });

  it('gives the placeholder for a missing value', () => {
    expect(formatDateTime(undefined, 'Not yet')).toBe('Not yet');
  });
});

describe('formatTime', () => {
  it('reads the time of day alone, in Pacific time on the 12-hour clock', () => {
    expect(formatTime('2026-09-27T10:07:00Z')).toBe('3:07 AM');
  });

  it('gives the placeholder for an unparseable value', () => {
    expect(formatTime('soon')).toBe('—');
  });
});

describe('formatMonth', () => {
  it('reads a YYYY-MM month as a short month and the year', () => {
    expect(formatMonth('2026-03')).toBe('Mar 2026');
  });

  it('reads December as the last month of its own year', () => {
    expect(formatMonth('2025-12')).toBe('Dec 2025');
  });

  it('gives back a value that is not a month unchanged', () => {
    expect(formatMonth('2026')).toBe('2026');
  });
});

describe('DateText', () => {
  it('renders the date as MM/DD/YYYY in a time element', () => {
    renderWithProviders(<DateText value="2026-09-27" />);
    expect(screen.getByText('09/27/2026')).toHaveAttribute('datetime', '2026-09-27');
  });

  it('renders the time of day in Pacific time on the 12-hour clock when asked', () => {
    renderWithProviders(<DateText value="2026-09-28T00:34:00Z" withTime />);
    expect(screen.getByText('09/27/2026 at 5:34 PM')).toBeInTheDocument();
  });

  it('sets its digits in the body face, not the mono face', () => {
    renderWithProviders(<DateText value="2026-09-27" />);
    expect(screen.getByText('09/27/2026')).toHaveClass('num');
  });

  it('keeps the mono face off a date', () => {
    renderWithProviders(<DateText value="2026-09-27" />);
    expect(screen.getByText('09/27/2026')).not.toHaveClass('mono');
  });

  it('renders the placeholder for a missing value', () => {
    renderWithProviders(<DateText value={null} placeholder="Lifetime" />);
    expect(screen.getByText('Lifetime')).toBeInTheDocument();
  });
});

describe('formatDateAt', () => {
  it('reads a moment in a named time zone as a date and a twelve-hour time', () => {
    expect(formatDateAt('2026-04-07T15:00:00Z', 'America/Los_Angeles')).toBe(
      '04/07/2026 at 8:00 AM',
    );
  });

  it('reads an afternoon time with PM', () => {
    expect(formatDateAt('2026-10-04T13:30', undefined)).toBe('10/04/2026 at 1:30 PM');
  });

  it('shows the placeholder for nothing', () => {
    expect(formatDateAt(null)).toBe('—');
  });
});
