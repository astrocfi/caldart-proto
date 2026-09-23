/**
 * Queries and pure summary arithmetic for the payments dashboard.
 *
 * The tiles deliberately ignore the filter bar: "this month" means this month
 * whatever the table below is showing.
 */
import { useQuery } from '@tanstack/react-query';
import type { UseQueryResult } from '@tanstack/react-query';

import { API_BASE, api } from '@/portal/api/client';
import type {
  Paginated,
  Payment,
  PaymentPeriodSummary,
  PaymentProvider,
  PaymentState,
} from '@/portal/api/types';

export type SummaryGroup = 'month' | 'year';

export interface PaymentFilterState {
  from: string;
  to: string;
  provider: PaymentProvider | '';
  status: PaymentState | '';
  search: string;
}

export const EMPTY_FILTERS: PaymentFilterState = {
  from: '',
  to: '',
  provider: '',
  status: '',
  search: '',
};

/** Filters as query parameters, dropping everything left blank. */
export function filterParams(filters: PaymentFilterState): Record<string, string> {
  const params: Record<string, string> = {};
  // `Object.keys` is typed `string[]` for soundness, but this interface is
  // closed, so narrowing the keys back to its own is safe here.
  for (const key of Object.keys(filters) as (keyof PaymentFilterState)[]) {
    const value = filters[key];
    if (value !== '') params[key] = value;
  }
  return params;
}

/** Turns filter parameters into a URL query string, or `''` when there are none. */
export function queryString(params: Record<string, string>): string {
  const search = new URLSearchParams(params).toString();
  return search ? `?${search}` : '';
}

/** The href the "Export CSV" button points at, honoring the filter bar. */
export function exportCsvUrl(filters: PaymentFilterState): string {
  return `${API_BASE}/admin/payments/export.csv${queryString(filterParams(filters))}`;
}

export interface ListOptions {
  page: number;
  pageSize: number;
  /** An `ordering` value the API accepts, e.g. `-paid_at`. */
  ordering: string;
}

/** The paginated payment list for `/admin/payments`, filtered, sorted, and paged. */
export function useAdminPayments(
  filters: PaymentFilterState,
  options: ListOptions,
): UseQueryResult<Paginated<Payment>> {
  const params = {
    ...filterParams(filters),
    ordering: options.ordering,
    page: String(options.page),
    page_size: String(options.pageSize),
  };
  return useQuery({
    queryKey: ['admin', 'payments', 'list', params],
    queryFn: () => api.get<Paginated<Payment>>(`/admin/payments${queryString(params)}`),
    placeholderData: (previous) => previous,
  });
}

/** The payment summary grouped by month or year, honoring the filter bar. */
export function useAdminPaymentSummary(
  group: SummaryGroup,
  filters: PaymentFilterState,
): UseQueryResult<PaymentPeriodSummary[]> {
  const params = { ...filterParams(filters), group };
  return useQuery({
    queryKey: ['admin', 'payments', 'summary', params],
    queryFn: () => api.get<PaymentPeriodSummary[]>(`/admin/payments/summary${queryString(params)}`),
  });
}

/** Unfiltered monthly summary, which the tiles are computed from. */
export function useMonthlyTotals(): UseQueryResult<PaymentPeriodSummary[]> {
  return useQuery({
    queryKey: ['admin', 'payments', 'summary', { group: 'month' }],
    queryFn: () => api.get<PaymentPeriodSummary[]>('/admin/payments/summary?group=month'),
  });
}

// --------------------------------------------------------------- tile math
export interface Totals {
  cents: number;
  count: number;
}

export const NO_TOTAL: Totals = { cents: 0, count: 0 };

function add(totals: Totals, row: PaymentPeriodSummary): Totals {
  return { cents: totals.cents + row.total_cents, count: totals.count + row.count };
}

/** `2026-03` for a date, matching the server's month period labels. */
export function monthKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

/** The `count` months ending with `today`, newest last. */
export function recentMonthKeys(count: number, today: Date): string[] {
  const keys: string[] = [];
  for (let back = count - 1; back >= 0; back -= 1) {
    keys.push(monthKey(new Date(today.getFullYear(), today.getMonth() - back, 1)));
  }
  return keys;
}

export interface DashboardTotals {
  thisMonth: Totals;
  yearToDate: Totals;
  lastTwelveMonths: Totals;
}

/** The three headline numbers, from the unfiltered monthly summary. */
export function dashboardTotals(
  rows: PaymentPeriodSummary[],
  today: Date = new Date(),
): DashboardTotals {
  const thisMonthKey = monthKey(today);
  const yearPrefix = `${today.getFullYear()}-`;
  const window = new Set(recentMonthKeys(12, today));

  let thisMonth = NO_TOTAL;
  let yearToDate = NO_TOTAL;
  let lastTwelveMonths = NO_TOTAL;

  for (const row of rows) {
    if (row.period === thisMonthKey) thisMonth = add(thisMonth, row);
    if (row.period.startsWith(yearPrefix)) yearToDate = add(yearToDate, row);
    if (window.has(row.period)) lastTwelveMonths = add(lastTwelveMonths, row);
  }

  return { thisMonth, yearToDate, lastTwelveMonths };
}

/** Providers that actually appear in a summary, in a stable order. */
export function providersIn(rows: PaymentPeriodSummary[]): PaymentProvider[] {
  const order: PaymentProvider[] = ['stripe', 'paypal', 'mock'];
  const seen = new Set<string>();
  for (const row of rows) {
    for (const provider of Object.keys(row.by_provider)) seen.add(provider);
  }
  return order.filter((provider) => seen.has(provider));
}
