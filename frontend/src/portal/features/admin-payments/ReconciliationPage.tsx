/**
 * `/admin/payments/reconciliation` — the books as a bank statement reads them.
 *
 * One row per month, per year or per provider, with the gross taken, what the
 * providers kept, what reached the bank, what went back, and how much of the
 * period has already been matched.  The two exports carry exactly the rows on
 * screen, so the figure a treasurer quotes is the figure they printed.
 */
import type { JSX } from 'react';

import type { ReconciliationRow } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { clearedValues, FilterBar } from '@/portal/components/FilterBar';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
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

/**
 * The table's columns.  The period identifies a row and never wraps; Gross and Net
 * stay in sight on a phone, and the rest drop, the least needed first, when the
 * table would not fit.  Every column sorts.
 */
function columns(group: ReconciliationGroup): Column<ReconciliationRow>[] {
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
      keepInSight: true,
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
      header: 'Matched',
      numeric: true,
      width: '6.5rem',
      dropOrder: 5,
      noWrap: true,
      render: matchedLabel,
      sortValue: (row) => row.reconciled_count,
    },
  ];
}

/**
 * The order the server lists the rows in, as the arrow the table opens on: oldest
 * period first, or none for the providers, which come in the server's own order.
 */
function defaultSort(group: ReconciliationGroup): { key: string; direction: 'asc' } | undefined {
  return group === 'provider' ? undefined : { key: 'period', direction: 'asc' };
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
      eyebrow="Payments"
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
        columns={columns(group)}
        initialSort={defaultSort(group)}
        rows={rows.data ?? []}
        rowKey={(row) => row.period}
        caption={`Takings by ${GROUP_LABELS[group].toLowerCase()}`}
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
          The reconciliation could not be loaded.
        </p>
      ) : null}
    </Page>
  );
}
