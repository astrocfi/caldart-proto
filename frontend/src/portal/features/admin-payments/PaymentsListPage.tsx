/**
 * `/admin/payments/list` — every payment, filtered, sorted, chosen and exported.
 *
 * The column chooser drives the table and both exports at once, so what a
 * treasurer sees is what the file they download will hold.  Sorting and paging
 * both go to the server, so ordering a column reorders the whole report rather
 * than just the page on screen; a column the server cannot order by has a plain
 * heading with no arrow.
 */
import { useMemo } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { usePlans } from '@/portal/api/queries';
import type { Payment, ReportColumn } from '@/portal/api/types';
import { Button, ButtonLink } from '@/portal/components/Button';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { clearedValues, FilterBar } from '@/portal/components/FilterBar';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import type { ReportCell } from '@/portal/components/reportTable';
import { ColumnTools, reportTableColumns, useColumnChoice } from '@/portal/components/reportTable';
import { StatusDot } from '@/portal/components/StatusDot';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import {
  useFirstPageWhenMissing,
  useUrlListPosition,
} from '@/portal/components/useUrlListPosition';
import { reportExportUrl } from '@/portal/reports/api';
import { REPORTS, listFilters } from '@/portal/reports/definitions';
import { useAdminPayments } from './api';
import { FinanceTabs } from './FinanceTabs';
import { KIND_LABELS, PROVIDER_LABELS, STATUS_LABELS, WALLET_LABELS, statusTone } from './labels';
import './admin-payments.css';

/**
 * The report's default columns, which the table shows while the registry loads or if it
 * cannot be read, so the table and the downloads still agree.
 */
const FALLBACK_COLUMNS: ReportColumn[] = [
  { key: 'paid_on', label: 'Date', default: true },
  { key: 'name', label: 'Name', default: true },
  { key: 'email', label: 'Email', default: true },
  { key: 'plan', label: 'Plan', default: true },
  { key: 'total', label: 'Total', default: true },
  { key: 'fee', label: 'Fee', default: true },
  { key: 'net', label: 'Net', default: true },
  { key: 'status', label: 'Status', default: true },
];

const PAGE_SIZE = 25;

const DEFAULT_ORDERING = '-paid_at';

const FILTER_FIELDS = listFilters(REPORTS.payments);
const FILTER_KEYS = FILTER_FIELDS.map((field) => field.key);

/**
 * How the table draws each export column, its width, and the `ordering` value behind
 * it where the API has one.
 *
 * The registry names the columns; this names the cells, so a column the server
 * adds shows up in the chooser and in the exports without the table pretending
 * to know how to render it.  The name identifies a row and stays pinned when the
 * table scrolls; Total and Status stay in sight on a phone; the rest drop, the
 * least needed first, when the table would not fit.
 */
const CELLS: Record<string, ReportCell<Payment>> = {
  paid_on: {
    ordering: 'paid_at',
    width: '7rem',
    noWrap: true,
    dropOrder: 7,
    render: (row) => <DateText value={row.paid_on} />,
  },
  receipt_number: {
    width: '9.5rem',
    noWrap: true,
    dropOrder: 6,
    render: (row) => <span className="num">{row.receipt_number}</span>,
  },
  name: {
    ordering: 'user__last_name',
    minWidth: '10rem',
    isIdentity: true,
    render: (row) => <Link to={`/admin/payments/${row.id}`}>{row.user_name}</Link>,
  },
  email: {
    ordering: 'user__email',
    minWidth: '12rem',
    dropOrder: 1,
    render: (row) => <a href={`mailto:${row.user_email}`}>{row.user_email}</a>,
  },
  plan: {
    ordering: 'plan__name',
    minWidth: '8rem',
    dropOrder: 3,
    render: (row) => row.plan ?? 'Contribution only',
  },
  kind: { minWidth: '8rem', dropOrder: 2, render: (row) => KIND_LABELS[row.kind] },
  plan_amount: {
    width: '6rem',
    numeric: true,
    dropOrder: 4,
    render: (row) => <Money cents={row.plan_amount_cents} />,
  },
  contribution: {
    ordering: 'contribution_cents',
    width: '7.5rem',
    numeric: true,
    dropOrder: 4,
    render: (row) => <Money cents={row.contribution_cents} />,
  },
  total: {
    ordering: 'amount_cents',
    width: '6rem',
    numeric: true,
    keepInSight: true,
    render: (row) => <Money cents={row.amount_cents} />,
  },
  fee: {
    ordering: 'fee_cents',
    width: '5.5rem',
    numeric: true,
    dropOrder: 5,
    render: (row) => <Money cents={row.fee_cents} />,
  },
  net: {
    ordering: 'net_cents',
    width: '6rem',
    numeric: true,
    dropOrder: 5,
    render: (row) => <Money cents={row.net_cents} />,
  },
  refunded: {
    width: '6.5rem',
    numeric: true,
    dropOrder: 4,
    render: (row) => <Money cents={row.refunded_cents} />,
  },
  provider: {
    ordering: 'provider',
    width: '6.5rem',
    dropOrder: 2,
    render: (row) => PROVIDER_LABELS[row.provider],
  },
  wallet: { width: '7rem', dropOrder: 2, render: (row) => WALLET_LABELS[row.wallet] },
  status: {
    ordering: 'status',
    width: '9rem',
    keepInSight: true,
    narrowWidth: '7rem',
    render: (row) => <StatusDot tone={statusTone(row.status)} label={STATUS_LABELS[row.status]} />,
  },
  provider_ref: {
    minWidth: '9rem',
    dropOrder: 1,
    render: (row) => <span className="num">{row.provider_ref}</span>,
  },
  received_on: {
    width: '7rem',
    noWrap: true,
    dropOrder: 3,
    render: (row) => <DateText value={row.received_on} />,
  },
  reconciled_on: {
    ordering: 'reconciled_on',
    width: '7rem',
    noWrap: true,
    dropOrder: 3,
    render: (row) => <DateText value={row.reconciled_on} />,
  },
  note: { minWidth: '10rem', dropOrder: 1, render: (row) => row.note },
  membership_starts: {
    width: '7rem',
    noWrap: true,
    dropOrder: 3,
    render: (row) => <DateText value={row.membership?.starts_on ?? null} />,
  },
  membership_ends: {
    width: '7rem',
    noWrap: true,
    dropOrder: 3,
    render: (row) => <DateText value={row.membership?.ends_on ?? null} />,
  },
};

/** The table's columns for the chosen keys, in registry order, sorted on the server. */
export function tableColumns(
  registry: readonly ReportColumn[],
  chosen: readonly string[],
): Column<Payment>[] {
  return reportTableColumns(registry, chosen, CELLS, true);
}

/** `/admin/payments/list`: the finance list with its filters, columns and exports. */
export function PaymentsListPage(): JSX.Element {
  const [filters, setFilters] = useUrlFilters(FILTER_KEYS);
  // The order and the page live in the address beside the filters.
  const position = useUrlListPosition(DEFAULT_ORDERING);
  const { ordering, page, setPage, sort, setSort: handleSortChange } = position;
  const choice = useColumnChoice('payments', FALLBACK_COLUMNS);

  const plans = usePlans();
  const planOptions = useMemo(
    () => ({ plan: (plans.data ?? []).map((plan) => ({ value: plan.slug, label: plan.name })) }),
    [plans.data],
  );

  const list = useAdminPayments(filters, { page, pageSize: PAGE_SIZE, ordering });
  useFirstPageWhenMissing(position, list.error);

  const tableCells = useMemo(
    () => tableColumns(choice.tableColumns, choice.tableChosen),
    [choice.tableColumns, choice.tableChosen],
  );
  const rows = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const exportParams = { ...filters, ordering, columns: choice.chosen };

  return (
    <Page
      title="Payments"
      lede="Every payment CalDART has taken, however it arrived."
      actions={<ButtonLink to="/admin/payments/record">Record a payment</ButtonLink>}
    >
      <FinanceTabs />

      <DataTable
        singleLine
        columns={tableCells}
        rows={rows}
        rowKey={(row) => row.id}
        caption={`${count} payment${count === 1 ? '' : 's'}`}
        filters={
          <FilterBar
            fields={FILTER_FIELDS}
            values={filters}
            onChange={(next) => setFilters(next)}
            options={planOptions}
            label="Filter payments"
          />
        }
        tools={<ColumnTools choice={choice} />}
        exportCsvUrl={reportExportUrl('payments', 'csv', exportParams)}
        exportPdfUrl={reportExportUrl('payments', 'pdf', exportParams)}
        isLoading={list.isPending}
        emptyTitle="No payments match these filters"
        emptyDescription="Try a wider date range, or reset the filters."
        emptyAction={
          <Button
            variant="secondary"
            onClick={() => setFilters(clearedValues(FILTER_FIELDS, filters))}
          >
            Reset filters
          </Button>
        }
        sort={sort}
        onSortChange={handleSortChange}
        pagination={{
          page,
          pageSize: PAGE_SIZE,
          count,
          onPageChange: setPage,
          label: 'Payment pages',
        }}
      />
    </Page>
  );
}
