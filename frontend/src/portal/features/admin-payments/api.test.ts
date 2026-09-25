import { describe, expect, it } from 'vitest';

import type { PaymentPeriodSummary } from '@/portal/api/types';
import {
  NO_TOTAL,
  dashboardTotals,
  filterParams,
  monthKey,
  providersIn,
  receiptUrl,
  recentMonthKeys,
  statementUrl,
  unrefundedCents,
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
    fee_cents: Math.round(total / 100),
    net_cents: total - Math.round(total / 100),
    refunded_cents: 0,
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
    expect(dashboardTotals(ROWS, TODAY).thisMonth.grossCents).toBe(5_000);
  });

  it('adds up the calendar year to date', () => {
    expect(dashboardTotals(ROWS, TODAY).yearToDate.grossCents).toBe(9_000);
  });

  it('adds up a rolling twelve months', () => {
    // April 2025 through March 2026: everything except 2025-02.
    expect(dashboardTotals(ROWS, TODAY).lastTwelveMonths.grossCents).toBe(14_000);
  });

  it('counts the payments behind a period', () => {
    expect(dashboardTotals(ROWS, TODAY).yearToDate.count).toBe(9);
  });

  it('adds up the fees the providers kept', () => {
    expect(dashboardTotals(ROWS, TODAY).yearToDate.feeCents).toBe(90);
  });

  it('adds up what reached the bank', () => {
    expect(dashboardTotals(ROWS, TODAY).yearToDate.netCents).toBe(8_910);
  });

  it('is all zeroes with no data', () => {
    expect(dashboardTotals([], TODAY)).toEqual({
      thisMonth: NO_TOTAL,
      yearToDate: NO_TOTAL,
      lastTwelveMonths: NO_TOTAL,
    });
  });
});

describe('month keys', () => {
  it('zero-pads the month', () => {
    expect(monthKey(new Date(2026, 0, 9))).toBe('2026-01');
  });

  it('keeps a two-digit month as it is', () => {
    expect(monthKey(new Date(2026, 11, 9))).toBe('2026-12');
  });

  it('walks back across a year boundary', () => {
    expect(recentMonthKeys(3, new Date(2026, 1, 1))).toEqual(['2025-12', '2026-01', '2026-02']);
  });
});

describe('providersIn', () => {
  it('lists only the providers present, in a stable order', () => {
    const rows = [
      row('2026-01', 10, 1, { paypal: 10 }),
      row('2026-02', 20, 1, { stripe: 20 }),
      row('2026-03', 30, 1, { manual: 30 }),
    ];
    expect(providersIn(rows)).toEqual(['stripe', 'paypal', 'manual']);
  });

  it('is empty for an empty summary', () => {
    expect(providersIn([])).toEqual([]);
  });
});

describe('filterParams', () => {
  it('drops blank values', () => {
    expect(filterParams({ provider: 'stripe', status: '', search: '' })).toEqual({
      provider: 'stripe',
    });
  });

  it('keeps every filter that is set', () => {
    expect(filterParams({ reconciled: 'no', kind: 'contribution' })).toEqual({
      kind: 'contribution',
      reconciled: 'no',
    });
  });
});

describe('download links', () => {
  it('points at one payment receipt', () => {
    expect(receiptUrl(412)).toBe('/api/v1/admin/payments/412/receipt.pdf');
  });

  it('points at one member statement for a year', () => {
    expect(statementUrl(37, 2026)).toBe('/api/v1/admin/payments/ledger/37/statements/2026.pdf');
  });
});

describe('unrefundedCents', () => {
  it('is the amount less what has already gone back', () => {
    expect(unrefundedCents({ amount_cents: 14_500, refunded_cents: 2_500 })).toBe(12_000);
  });

  it('never goes below zero', () => {
    expect(unrefundedCents({ amount_cents: 4_500, refunded_cents: 5_000 })).toBe(0);
  });
});
