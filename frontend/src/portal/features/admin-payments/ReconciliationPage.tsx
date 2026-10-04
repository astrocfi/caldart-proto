/**
 * `/admin/payments/reconciliation` — the books as a bank statement reads them.
 *
 * One row per month, per year or per provider, newest first, with the gross taken,
 * what the providers kept, what reached the bank, what went back, and how much of the
 * period has already been matched, and a totals row under them to check against the
 * statement.  A period not fully matched links to its payments still waiting.  The two
 * exports carry exactly the rows on screen, so the figure a treasurer quotes is the
 * figure they printed.
 */
import type { JSX, ReactNode } from 'react';
import { Link } from 'react-router-dom';

import type { ReconciliationRow } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { clearedValues, FilterBar } from '@/portal/components/FilterBar';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import type { FilterValues } from '@/portal/reports/types';
import { reportExportUrl } from '@/portal/reports/api';
import { REPORTS, listFilters } from '@/portal/reports/definitions';
import { FinanceTabs } from './FinanceTabs';
import {
  DEFAULT_RECONCILIATION_GROUP,
  reconciliationPeriodLabel,
  useReconciliation,
} from './reports-api';
import type { ReconciliationGroup } from './reports-api';
import './admin-payments.css';

const FILTER_FIELDS = listFilters(REPORTS.reconciliation);
const FILTER_KEYS = FILTER_FIELDS.map((field) => field.key);

const GROUP_LABELS: Record<ReconciliationGroup, string> = {
  month: 'Month',
  year: 'Year',
  provider: 'Provider',
};

/** How much of a period a treasurer has already found on the statement. */
export function matchedLabel(row: ReconciliationRow): string {
  return `${row.reconciled_count} of ${row.count}`;
}

/** The later of two ISO dates, either of which may be blank. */
function laterOf(a: string, b: string): string {
  return a > b ? a : b;
}

/** The earlier of two ISO dates, a blank one counting as no bound at all. */
function earlierOf(a: string, b: string): string {
  if (a === '') return b;
  if (b === '') return a;
  return a < b ? a : b;
}

/** The first and last day of a `2026-03` month or a `2026` year. */
function periodBounds(period: string, group: 'month' | 'year'): { from: string; to: string } {
  if (group === 'year') return { from: `${period}-01-01`, to: `${period}-12-31` };
  const [year, month] = period.split('-').map(Number);
  const lastDay = new Date(year ?? 0, month ?? 0, 0).getDate();
  return { from: `${period}-01`, to: `${period}-${String(lastDay).padStart(2, '0')}` };
}

/**
 * The payment list, narrowed to the payments of `row` still waiting to be matched: the
 * row's period within the range on screen (or the whole range and the row's provider,
 * by provider), the provider chosen, and **Not reconciled**.
 */
export function unmatchedPaymentsUrl(
  row: ReconciliationRow,
  group: ReconciliationGroup,
  filters: FilterValues,
): string {
  const chosenFrom = filters.from ?? '';
  const chosenTo = filters.to ?? '';
  const range =
    group === 'provider' ? { from: chosenFrom, to: chosenTo } : periodBounds(row.period, group);
  const params = new URLSearchParams();
  const from = laterOf(range.from, chosenFrom);
  const to = earlierOf(range.to, chosenTo);
  if (from !== '') params.set('from', from);
  if (to !== '') params.set('to', to);
  const provider = group === 'provider' ? row.period : (filters.provider ?? '');
  if (provider !== '') params.set('provider', provider);
  params.set('reconciled', 'no');
  return `/admin/payments/list?${params.toString()}`;
}

/** The Reconciled figure, as a link to the payments still waiting when any are. */
function matchedCell(
  row: ReconciliationRow,
  group: ReconciliationGroup,
  filters: FilterValues,
): ReactNode {
  if (row.unreconciled_count === 0) return matchedLabel(row);
  const period = reconciliationPeriodLabel(row.period, group);
  return (
    <Link to={unmatchedPaymentsUrl(row, group, filters)}>
      {matchedLabel(row)}
      <span className="visually-hidden">
        {` reconciled, ${period}: the ${row.unreconciled_count} not reconciled`}
      </span>
    </Link>
  );
}

/** The figures every row carries, summed for the totals row. */
const SUMMED: readonly (keyof Omit<ReconciliationRow, 'period'>)[] = [
  'count',
  'gross_cents',
  'fee_cents',
  'net_cents',
  'refunded_cents',
  'net_after_refunds_cents',
  'reconciled_count',
  'unreconciled_count',
];

/** Every figure of `rows` added up, for the totals row. */
export function reconciliationTotals(rows: readonly ReconciliationRow[]): ReconciliationRow {
  const totals: ReconciliationRow = {
    period: '',
    count: 0,
    gross_cents: 0,
    fee_cents: 0,
    net_cents: 0,
    refunded_cents: 0,
    net_after_refunds_cents: 0,
    reconciled_count: 0,
    unreconciled_count: 0,
  };
  for (const row of rows) {
    for (const key of SUMMED) totals[key] += row[key];
  }
  return totals;
}

/** The totals row's cells, keyed by the columns they sit under. */
function totalsFooter(rows: readonly ReconciliationRow[]): Record<string, ReactNode> {
  const totals = reconciliationTotals(rows);
  return {
    period: 'Total',
    count: totals.count,
    gross_cents: <Money cents={totals.gross_cents} />,
    fee_cents: <Money cents={totals.fee_cents} />,
    net_cents: <Money cents={totals.net_cents} />,
    refunded_cents: <Money cents={totals.refunded_cents} />,
    net_after_refunds_cents: <Money cents={totals.net_after_refunds_cents} />,
    matched: matchedLabel(totals),
  };
}

/**
 * The table's columns.  The period identifies a row and never wraps; Net and the
 * Reconciled figure, whose link is what the page is for, stay in sight on a phone, and
 * the rest drop, the least needed first and Gross last, when the table would not fit.
 * Every column sorts.
 */
function columns(group: ReconciliationGroup, filters: FilterValues): Column<ReconciliationRow>[] {
  return [
    {
      key: 'period',
      header: GROUP_LABELS[group],
      width: '8rem',
      isIdentity: true,
      render: (row) => reconciliationPeriodLabel(row.period, group),
      sortValue: (row) => row.period,
    },
    {
      key: 'count',
      header: 'Payments',
      numeric: true,
      width: '6.5rem',
      dropOrder: 4,
      render: (row) => row.count,
      sortValue: (row) => row.count,
    },
    {
      key: 'gross_cents',
      header: 'Gross',
      numeric: true,
      width: '7.5rem',
      dropOrder: 6,
      render: (row) => <Money cents={row.gross_cents} />,
      sortValue: (row) => row.gross_cents,
    },
    {
      key: 'fee_cents',
      header: 'Fees',
      numeric: true,
      width: '6.5rem',
      dropOrder: 3,
      render: (row) => <Money cents={row.fee_cents} />,
      sortValue: (row) => row.fee_cents,
    },
    {
      key: 'net_cents',
      header: 'Net',
      numeric: true,
      width: '7.5rem',
      keepInSight: true,
      render: (row) => <Money cents={row.net_cents} />,
      sortValue: (row) => row.net_cents,
    },
    {
      key: 'refunded_cents',
      header: 'Refunded',
      numeric: true,
      width: '7rem',
      dropOrder: 1,
      render: (row) => <Money cents={row.refunded_cents} />,
      sortValue: (row) => row.refunded_cents,
    },
    {
      key: 'net_after_refunds_cents',
      header: 'Net after refunds',
      numeric: true,
      width: '10rem',
      dropOrder: 2,
      render: (row) => <Money cents={row.net_after_refunds_cents} />,
      sortValue: (row) => row.net_after_refunds_cents,
    },
    {
      key: 'matched',
      header: 'Reconciled',
      numeric: true,
      width: '6.5rem',
      keepInSight: true,
      noWrap: true,
      render: (row) => matchedCell(row, group, filters),
      sortValue: (row) => row.reconciled_count,
    },
  ];
}

/**
 * The order the server lists the rows in, as the arrow the table opens on: newest
 * period first, as the money overview runs, or none for the providers, which come in
 * the server's own order.
 */
function defaultSort(group: ReconciliationGroup): { key: string; direction: 'desc' } | undefined {
  return group === 'provider' ? undefined : { key: 'period', direction: 'desc' };
}

/** The grouping a `group` value asks for, the server's own when it is blank or unknown. */
function groupOf(value: string | undefined): ReconciliationGroup {
  return value === 'year' || value === 'provider' ? value : DEFAULT_RECONCILIATION_GROUP;
}

/** The Reconciliation tab of the finance area. */
export function ReconciliationPage(): JSX.Element {
  const [filters, setFilters] = useUrlFilters(FILTER_KEYS);
  const group = groupOf(filters.group);

  const rows = useReconciliation(filters);

  return (
    <Page
      title="Reconciliation"
      lede="What the books say arrived, period by period, for matching against a statement."
    >
      <FinanceTabs />

      <p className="muted">
        A payment counts in the period the money arrived; a refund counts in the period it was
        taken. Set a payment&rsquo;s reconciled date on its own screen once you have found it on the
        statement.
      </p>

      <DataTable
        key={group}
        singleLine
        columns={columns(group, filters)}
        initialSort={defaultSort(group)}
        rows={rows.data ?? []}
        footer={rows.data === undefined ? undefined : totalsFooter(rows.data)}
        rowKey={(row) => row.period}
        caption={`Money in by ${GROUP_LABELS[group].toLowerCase()}`}
        filters={
          <FilterBar
            fields={FILTER_FIELDS}
            values={filters}
            onChange={(next) => setFilters(next)}
            label="Filter the reconciliation"
          />
        }
        exportCsvUrl={reportExportUrl('reconciliation', 'csv', filters)}
        exportPdfUrl={reportExportUrl('reconciliation', 'pdf', filters)}
        isLoading={rows.isPending}
        emptyTitle="Nothing was taken in this range"
        emptyDescription="Widen the dates, or reset the filters to see every period."
        emptyAction={
          <Button
            variant="secondary"
            onClick={() => setFilters(clearedValues(FILTER_FIELDS, filters))}
          >
            Reset filters
          </Button>
        }
      />

      {rows.isError ? (
        <p role="alert" className="field__error">
          The reconciliation didn&apos;t load. Try again in a moment.
        </p>
      ) : null}
    </Page>
  );
}
