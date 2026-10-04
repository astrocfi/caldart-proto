/**
 * Money per month or per year, with one column per provider.
 *
 * Newest first: an administrator looking at this page almost always wants the
 * period they are in.  On a phone the provider columns and the other figures drop
 * away, so the Total stays beside the period.
 */
import type { JSX, ReactNode } from 'react';

import type { PaymentPeriodSummary, PaymentProvider } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { formatMonth } from '@/portal/components/DateText';
import { formatCents } from '@/portal/components/Money';
import { PROVIDER_LABELS } from './labels';
import { providersIn } from './api';
import type { SummaryGroup } from './api';

export interface PeriodTableProps {
  rows: PaymentPeriodSummary[];
  group: SummaryGroup;
  onGroupChange: (group: SummaryGroup) => void;
  isLoading?: boolean;
  /** Filter controls rendered between the heading and the table. */
  filters?: ReactNode;
  /** Empties the filters, offered from an empty table as **Reset filters**. */
  onResetFilters?: () => void;
}

/** `2026-03` -> `Mar 2026`, three letters so no month wraps; `2026` is already readable. */
export function periodLabel(period: string, group: SummaryGroup): string {
  return group === 'year' ? period : formatMonth(period);
}

/**
 * A money column: right-aligned, sortable, and dropped in `dropOrder` on a narrow
 * screen.  A period `cents` gives nothing for reads as a dash.
 */
function moneyColumn(
  key: string,
  header: string,
  cents: (row: PaymentPeriodSummary) => number | undefined,
  dropOrder: number,
): Column<PaymentPeriodSummary> {
  return {
    key,
    header,
    numeric: true,
    width: '7.5rem',
    dropOrder,
    render: (row) => {
      const value = cents(row);
      return value === undefined ? '—' : formatCents(value);
    },
    sortValue: (row) => cents(row) ?? 0,
  };
}

/**
 * The table's columns: the period, which identifies a row and never wraps; the
 * count, the dues, the contributions, one column per provider, the fees, the net,
 * and the refunds, which drop on a narrow screen, the providers first; and the Total,
 * which stays in sight beside the period on a phone.
 */
function periodColumns(
  group: SummaryGroup,
  providers: readonly PaymentProvider[],
): Column<PaymentPeriodSummary>[] {
  return [
    {
      key: 'period',
      header: group === 'month' ? 'Month' : 'Year',
      width: '7rem',
      isIdentity: true,
      render: (row) => periodLabel(row.period, group),
      sortValue: (row) => row.period,
    },
    {
      key: 'count',
      header: 'Payments',
      numeric: true,
      width: '6.5rem',
      dropOrder: 3,
      render: (row) => row.count,
      sortValue: (row) => row.count,
    },
    moneyColumn('plan_cents', 'Dues', (row) => row.plan_cents, 2),
    {
      ...moneyColumn('contribution_cents', 'Contributions', (row) => row.contribution_cents, 2),
      width: '9rem',
    },
    ...providers.map((provider) =>
      moneyColumn(
        `provider_${provider}`,
        PROVIDER_LABELS[provider],
        (row) => row.by_provider[provider] || undefined,
        1,
      ),
    ),
    moneyColumn('fee_cents', 'Fees', (row) => row.fee_cents, 5),
    moneyColumn('net_cents', 'Net', (row) => row.net_cents, 6),
    moneyColumn('refunded_cents', 'Refunded', (row) => row.refunded_cents, 4),
    {
      ...moneyColumn('total_cents', 'Total', (row) => row.total_cents, 0),
      dropOrder: undefined,
      keepInSight: true,
      render: (row) => <span className="period-table__total">{formatCents(row.total_cents)}</span>,
    },
  ];
}

/** The order the table opens on, newest period first. */
const NEWEST_FIRST = { key: 'period', direction: 'desc' } as const;

/** Money per month or year, with one column per payment provider, newest first. */
export function PeriodTable({
  rows,
  group,
  onGroupChange,
  isLoading = false,
  filters,
  onResetFilters: handleResetFilters,
}: PeriodTableProps): JSX.Element {
  const providers = providersIn(rows);
  const newestFirst = [...rows].reverse();
  const resetButton =
    handleResetFilters === undefined ? undefined : (
      <Button variant="secondary" onClick={handleResetFilters}>
        Reset filters
      </Button>
    );

  return (
    <section className="stack period-table" aria-labelledby="payments-by-period">
      <div className="period-table__bar">
        <h2 className="period-table__title" id="payments-by-period">
          Payments by period
        </h2>
        <div className="segmented" role="group" aria-label="Group payments by">
          {(['month', 'year'] as SummaryGroup[]).map((option) => (
            <button
              key={option}
              type="button"
              className="segmented__option"
              aria-pressed={group === option}
              onClick={() => onGroupChange(option)}
            >
              {option === 'month' ? 'Month' : 'Year'}
            </button>
          ))}
        </div>
      </div>

      <DataTable
        key={group}
        singleLine
        columns={periodColumns(group, providers)}
        rows={newestFirst}
        rowKey={(row) => row.period}
        caption={`Payment totals by ${group}`}
        initialSort={NEWEST_FIRST}
        filters={filters}
        isLoading={isLoading}
        emptyTitle="No payments in this range"
        emptyDescription="Widen the dates, or reset the filters to see everything."
        emptyAction={resetButton}
      />
    </section>
  );
}
