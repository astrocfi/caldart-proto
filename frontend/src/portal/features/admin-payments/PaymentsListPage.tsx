/**
 * `/admin/payments/list` — every payment, filtered, sorted, chosen and exported.
 *
 * The column chooser drives the table and both exports at once, so what a
 * treasurer sees is what the file they download will hold.  Sorting and paging
 * both go to the server, so ordering a column reorders the whole report rather
 * than just the page on screen.
 */
import { useMemo, useState } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { Payment, ReportColumn } from '@/portal/api/types';
import { Button, ButtonLink } from '@/portal/components/Button';
import { ColumnChooser, defaultColumnKeys } from '@/portal/components/ColumnChooser';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { StatusChip } from '@/portal/components/StatusChip';
import { useDebounced } from '@/portal/components/useDebounced';
import { EMPTY_FILTERS, exportUrl, useAdminPayments, useReportColumns } from './api';
import type { PaymentFilterState } from './api';
import { FilterBar } from './FilterBar';
import { FinanceTabs } from './FinanceTabs';
import { KIND_LABELS, PROVIDER_LABELS, STATUS_LABELS, WALLET_LABELS, statusTone } from './labels';
import './admin-payments.css';

const PAGE_SIZE = 25;

const DEFAULT_ORDERING = '-paid_at';

/**
 * How the table draws each export column, and the `ordering` value behind it.
 *
 * The registry names the columns; this names the cells, so a column the server
 * adds shows up in the chooser and in the exports without the table pretending
 * to know how to render it.
 */
const CELLS: Record<string, Omit<Column<Payment>, 'key' | 'header'>> = {
  paid_on: { render: (row) => <DateText value={row.paid_on} /> },
  receipt_number: { render: (row) => <span className="mono">{row.receipt_number}</span> },
  name: {
    render: (row) => <Link to={`/admin/payments/${row.id}`}>{row.user_name}</Link>,
  },
  email: { render: (row) => <a href={`mailto:${row.user_email}`}>{row.user_email}</a> },
  plan: { render: (row) => row.plan ?? 'Contribution only' },
  kind: { render: (row) => KIND_LABELS[row.kind] },
  plan_amount: { numeric: true, render: (row) => <Money cents={row.plan_amount_cents} /> },
  contribution: { numeric: true, render: (row) => <Money cents={row.contribution_cents} /> },
  total: { numeric: true, render: (row) => <Money cents={row.amount_cents} /> },
  fee: { numeric: true, render: (row) => <Money cents={row.fee_cents} /> },
  net: { numeric: true, render: (row) => <Money cents={row.net_cents} /> },
  refunded: { numeric: true, render: (row) => <Money cents={row.refunded_cents} /> },
  provider: { render: (row) => PROVIDER_LABELS[row.provider] },
  wallet: { render: (row) => WALLET_LABELS[row.wallet] },
  status: {
    render: (row) => <StatusChip tone={statusTone(row.status)} label={STATUS_LABELS[row.status]} />,
  },
  provider_ref: { render: (row) => <span className="mono">{row.provider_ref}</span> },
  received_on: { render: (row) => <DateText value={row.received_on} /> },
  reconciled_on: { render: (row) => <DateText value={row.reconciled_on} /> },
  note: { render: (row) => row.note },
  membership_starts: { render: (row) => <DateText value={row.membership?.starts_on ?? null} /> },
  membership_ends: { render: (row) => <DateText value={row.membership?.ends_on ?? null} /> },
};

/** The `ordering` value each column sorts by, where the API has one. */
const ORDERING: Record<string, string> = {
  paid_on: 'paid_at',
  name: 'user__last_name',
  email: 'user__email',
  plan: 'plan__name',
  contribution: 'contribution_cents',
  total: 'amount_cents',
  fee: 'fee_cents',
  net: 'net_cents',
  status: 'status',
  provider: 'provider',
  reconciled_on: 'reconciled_on',
};

/** The table's columns for the chosen keys, in registry order. */
export function tableColumns(registry: ReportColumn[], chosen: string[]): Column<Payment>[] {
  return registry
    .filter((column) => chosen.includes(column.key))
    .map((column) => {
      const cell = CELLS[column.key] ?? { render: () => '—' };
      const sortKey = ORDERING[column.key];
      return {
        ...cell,
        key: sortKey ?? column.key,
        header: column.label,
        sortable: sortKey !== undefined,
      };
    });
}

/** `/admin/payments/list`: the finance list with its filters, columns and exports. */
export function PaymentsListPage(): JSX.Element {
  const [filters, setFilters] = useState<PaymentFilterState>(EMPTY_FILTERS);
  const [chosen, setChosen] = useState<string[] | null>(null);
  const [page, setPage] = useState(1);
  const [ordering, setOrdering] = useState(DEFAULT_ORDERING);

  const registry = useReportColumns();
  const columns = useMemo(() => registry.data ?? [], [registry.data]);
  const chosenKeys = chosen ?? defaultColumnKeys(columns);

  // The search box types into the filter state, but only a settled term is
  // worth a request, so the query lags the box by the debounce.
  const settledSearch = useDebounced(filters.search);
  const queried = useMemo(() => ({ ...filters, search: settledSearch }), [filters, settledSearch]);
  const list = useAdminPayments(queried, { page, pageSize: PAGE_SIZE, ordering });

  const tableCells = useMemo(() => tableColumns(columns, chosenKeys), [columns, chosenKeys]);
  const rows = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const lastPage = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const exportOptions = { columns: chosenKeys, ordering };

  function handleColumnChange(next: string[]) {
    setChosen(next);
  }

  function handleFilterChange(next: PaymentFilterState) {
    setFilters(next);
    setPage(1);
  }

  return (
    <Page
      title="Payments"
      eyebrow="Finance"
      lede="Every payment CalDART has taken, however it arrived."
      actions={<ButtonLink to="/admin/payments/record">Record a payment</ButtonLink>}
    >
      <FinanceTabs />

      <DataTable
        columns={tableCells}
        rows={rows}
        rowKey={(row) => row.id}
        caption={`${count} payment${count === 1 ? '' : 's'}`}
        filters={
          <>
            <FilterBar value={filters} onChange={handleFilterChange} />
            <ColumnChooser columns={columns} chosen={chosenKeys} onChange={handleColumnChange} />
          </>
        }
        exportCsvUrl={exportUrl('csv', queried, exportOptions)}
        exportPdfUrl={exportUrl('pdf', queried, exportOptions)}
        isLoading={list.isPending}
        emptyTitle="No payments match these filters"
        emptyDescription="Try a wider date range, or clear the filters."
        initialSort={{ key: 'paid_at', direction: 'desc' }}
        onSortChange={(key, direction) => {
          setOrdering(`${direction === 'desc' ? '-' : ''}${key}`);
          setPage(1);
        }}
      />

      {lastPage > 1 ? (
        <nav className="pager" aria-label="Payment pages">
          <Button
            variant="quiet"
            small
            disabled={page <= 1}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            Previous
          </Button>
          <span className="muted pager__status" aria-live="polite">
            Page {page} of {lastPage}
          </span>
          <Button
            variant="quiet"
            small
            disabled={page >= lastPage}
            onClick={() => setPage((current) => Math.min(lastPage, current + 1))}
          >
            Next
          </Button>
        </nav>
      ) : null}
    </Page>
  );
}
