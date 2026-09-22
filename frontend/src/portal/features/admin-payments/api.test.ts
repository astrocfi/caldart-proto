import { describe, expect, it } from 'vitest';

import type { PaymentPeriodSummary } from '@/portal/api/types';
import {
  EMPTY_FILTERS,
  dashboardTotals,
  exportCsvUrl,
  filterParams,
  monthKey,
  providersIn,
  recentMonthKeys,
} from './api';

function row(
  period: string,
  total: number,
  count: number,
  by: Record<string, number> = {},
): PaymentPeriodSummary {
  return {
    period,
    count,
    total_cents: total,
    plan_cents: total,
    contribution_cents: 0,
    by_provider: by,
  };
}

/** 15 March 2026, so "this month", "this year" and "last 12" all differ. */
const TODAY = new Date(2026, 2, 15);

describe('dashboardTotals', () => {
  const ROWS = [
    row('2025-02', 1_000, 1), // outside the 12-month window
    row('2025-04', 2_000, 2),
    row('2025-12', 3_000, 3),
    row('2026-01', 4_000, 4),
    row('2026-03', 5_000, 5),
  ];

  it('adds up the current month', () => {
    expect(dashboardTotals(ROWS, TODAY).thisMonth).toEqual({ cents: 5_000, count: 5 });
  });

  it('adds up the calendar year to date', () => {
    expect(dashboardTotals(ROWS, TODAY).yearToDate).toEqual({ cents: 9_000, count: 9 });
  });

  it('adds up a rolling twelve months', () => {
    // April 2025 through March 2026: everything except 2025-02.
    expect(dashboardTotals(ROWS, TODAY).lastTwelveMonths).toEqual({ cents: 14_000, count: 14 });
  });

  it('is all zeroes with no data', () => {
    expect(dashboardTotals([], TODAY)).toEqual({
      thisMonth: { cents: 0, count: 0 },
      yearToDate: { cents: 0, count: 0 },
      lastTwelveMonths: { cents: 0, count: 0 },
    });
  });
});

describe('month keys', () => {
  it('zero-pads the month', () => {
    expect(monthKey(new Date(2026, 0, 9))).toBe('2026-01');
    expect(monthKey(new Date(2026, 11, 9))).toBe('2026-12');
  });

  it('walks back across a year boundary', () => {
    expect(recentMonthKeys(3, new Date(2026, 1, 1))).toEqual(['2025-12', '2026-01', '2026-02']);
  });
});

describe('providersIn', () => {
  it('lists only the providers present, in a stable order', () => {
    const rows = [row('2026-01', 10, 1, { paypal: 10 }), row('2026-02', 20, 1, { stripe: 20 })];
    expect(providersIn(rows)).toEqual(['stripe', 'paypal']);
  });

  it('is empty for an empty summary', () => {
    expect(providersIn([])).toEqual([]);
  });
});

describe('filters', () => {
  it('drops blank values', () => {
    expect(filterParams({ ...EMPTY_FILTERS, provider: 'stripe' })).toEqual({ provider: 'stripe' });
  });

  it('builds an export URL that carries the filters', () => {
    const url = exportCsvUrl({
      from: '2026-01-01',
      to: '2026-03-31',
      provider: 'paypal',
      status: 'succeeded',
      search: 'reyes',
    });
    expect(url).toBe(
      '/api/v1/admin/payments/export.csv' +
        '?from=2026-01-01&to=2026-03-31&provider=paypal&status=succeeded&search=reyes',
    );
  });

  it('exports everything when nothing is filtered', () => {
    expect(exportCsvUrl(EMPTY_FILTERS)).toBe('/api/v1/admin/payments/export.csv');
  });
});
