/**
 * `/admin/payments/reconciliation` — the books as a bank statement reads them.
 *
 * One row per month, per year or per provider, with the gross taken, what the
 * providers kept, what reached the bank, what went back, and how much of the
 * period has already been matched.  The two exports carry exactly the rows on
 * screen, so the figure a treasurer quotes is the figure they printed.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { PaymentProvider, ReconciliationRow } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { Field } from '@/portal/components/Field';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { PROVIDER_LABELS } from './labels';
import {
  EMPTY_RECONCILIATION_FILTERS,
  RECONCILIATION_GROUPS,
  reconciliationExportUrl,
  reconciliationPeriodLabel,
  useReconciliation,
} from './reports-api';
import type { ReconciliationFilterState, ReconciliationGroup } from './reports-api';
import './admin-payments.css';

const PROVIDERS: PaymentProvider[] = ['stripe', 'paypal', 'mock', 'manual'];

const GROUP_LABELS: Record<ReconciliationGroup, string> = {
  month: 'Month',
  year: 'Year',
  provider: 'Provider',
};

const PERIOD_HEADERS: Record<ReconciliationGroup, string> = {
  month: 'Month',
  year: 'Year',
  provider: 'Provider',
};

/** How much of a period a treasurer has already found on the statement. */
export function matchedLabel(row: ReconciliationRow): string {
  return `${row.reconciled_count} of ${row.count}`;
}

function columns(group: ReconciliationGroup): Column<ReconciliationRow>[] {
  return [
    {
      key: 'period',
      header: PERIOD_HEADERS[group],
      render: (row) => reconciliationPeriodLabel(row.period, group),
      sortValue: (row) => row.period,
    },
    { key: 'count', header: 'Payments', numeric: true, render: (row) => row.count },
    {
      key: 'gross_cents',
      header: 'Gross',
      numeric: true,
      render: (row) => <Money cents={row.gross_cents} />,
      sortValue: (row) => row.gross_cents,
    },
    {
      key: 'fee_cents',
      header: 'Fees',
      numeric: true,
      render: (row) => <Money cents={row.fee_cents} />,
      sortValue: (row) => row.fee_cents,
    },
    {
      key: 'net_cents',
      header: 'Net',
      numeric: true,
      render: (row) => <Money cents={row.net_cents} />,
      sortValue: (row) => row.net_cents,
    },
    {
      key: 'refunded_cents',
      header: 'Refunded',
      numeric: true,
      render: (row) => <Money cents={row.refunded_cents} />,
      sortValue: (row) => row.refunded_cents,
    },
    {
      key: 'net_after_refunds_cents',
      header: 'Net after refunds',
      numeric: true,
      render: (row) => <Money cents={row.net_after_refunds_cents} />,
      sortValue: (row) => row.net_after_refunds_cents,
    },
    { key: 'matched', header: 'Matched', numeric: true, render: matchedLabel },
  ];
}

/** The Reconciliation tab of the finance area. */
export function ReconciliationPage(): JSX.Element {
  const [filters, setFilters] = useState<ReconciliationFilterState>(EMPTY_RECONCILIATION_FILTERS);
  const [group, setGroup] = useState<ReconciliationGroup>('month');

  const rows = useReconciliation(filters, group);

  function set<K extends keyof ReconciliationFilterState>(
    key: K,
    value: ReconciliationFilterState[K],
  ): void {
    setFilters({ ...filters, [key]: value });
  }

  const isFiltered = Object.values(filters).some((value) => value !== '');

  const filterBar = (
    <div className="payment-filters">
      <Field label="From">
        {(props) => (
          <input
            {...props}
            type="date"
            value={filters.from}
            onChange={(event) => set('from', event.target.value)}
          />
        )}
      </Field>
      <Field label="To">
        {(props) => (
          <input
            {...props}
            type="date"
            value={filters.to}
            onChange={(event) => set('to', event.target.value)}
          />
        )}
      </Field>
      <Field label="Provider">
        {(props) => (
          <select
            {...props}
            value={filters.provider}
            onChange={(event) => set('provider', event.target.value as PaymentProvider | '')}
          >
            <option value="">Any provider</option>
            {PROVIDERS.map((provider) => (
              <option key={provider} value={provider}>
                {PROVIDER_LABELS[provider]}
              </option>
            ))}
          </select>
        )}
      </Field>
      <div className="segmented" role="group" aria-label="Group takings by">
        {RECONCILIATION_GROUPS.map((option) => (
          <button
            key={option}
            type="button"
            className="segmented__option"
            aria-pressed={group === option}
            onClick={() => setGroup(option)}
          >
            {GROUP_LABELS[option]}
          </button>
        ))}
      </div>
      {isFiltered ? (
        <Button variant="quiet" small onClick={() => setFilters(EMPTY_RECONCILIATION_FILTERS)}>
          Clear filters
        </Button>
      ) : null}
    </div>
  );

  return (
    <Page
      title="Reconciliation"
      eyebrow="Payments"
      lede="What the books say arrived, period by period, for matching against a statement."
    >
      <p className="muted">
        A payment counts in the period the money arrived; a refund counts in the period it was
        taken. Set a payment&rsquo;s reconciled date on its own screen once you have found it on the
        statement.
      </p>

      <DataTable
        columns={columns(group)}
        rows={rows.data ?? []}
        rowKey={(row) => row.period}
        caption={`Takings by ${GROUP_LABELS[group].toLowerCase()}`}
        filters={filterBar}
        exportCsvUrl={reconciliationExportUrl(filters, group, 'csv')}
        exportPdfUrl={reconciliationExportUrl(filters, group, 'pdf')}
        isLoading={rows.isPending}
        emptyTitle="Nothing was taken in this range"
        emptyDescription="Widen the dates, or clear the filters to see every period."
      />

      {rows.isError ? (
        <p role="alert" className="field__error">
          The reconciliation could not be loaded.
        </p>
      ) : null}
    </Page>
  );
}
