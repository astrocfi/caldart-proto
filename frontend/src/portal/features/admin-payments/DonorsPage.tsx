/**
 * `/admin/payments/donors` — everyone who has given through the public
 * donation page, for the treasurer alone.
 *
 * One row per donor, aggregated over the range the filter bar narrows to:
 * how much they have given, how much of it came back, and when they last
 * gave.  An account administrator does not reach this screen; the route
 * guard and `FinanceTabs` both key off the treasurer role.  A donor is on no
 * member list, so for a reader who also opens member records (an account
 * administrator, or a system administrator) each name links to the donor's
 * record, where the donor can be deleted; a "Deleted member N" row is not linked.  The column
 * chooser drives the table and both exports at once, so what a treasurer
 * sees is what the downloaded file holds, as `PaymentsListPage` does.
 */
import { useMemo } from 'react';
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { DonorRow, ReportColumn } from '@/portal/api/types';
import { useDarts } from '@/portal/api/queries';
import { useAuth } from '@/portal/auth/useAuth';
import { Button } from '@/portal/components/Button';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { clearedValues, FilterBar } from '@/portal/components/FilterBar';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import type { ReportCell } from '@/portal/components/reportTable';
import { ColumnTools, reportTableColumns, useColumnChoice } from '@/portal/components/reportTable';
import { StatusChip } from '@/portal/components/StatusChip';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import { hasAnyRole } from '@/portal/nav';
import { reportExportUrl } from '@/portal/reports/api';
import { REPORTS, listFilters } from '@/portal/reports/definitions';
import { useDonors } from './api';
import { FinanceTabs } from './FinanceTabs';
import './admin-payments.css';

/**
 * The columns the table shows while the report's registry loads, or if it cannot be read:
 * the donor, how to reach them, and what they gave.
 */
const FALLBACK_COLUMNS: ReportColumn[] = [
  { key: 'name', label: 'Name', default: true },
  { key: 'email', label: 'Email', default: true },
  { key: 'given', label: 'Given', default: true },
  { key: 'net', label: 'Net', default: true },
];

const FILTER_FIELDS = listFilters(REPORTS.donors);
const FILTER_KEYS = FILTER_FIELDS.map((field) => field.key);

/**
 * How the table draws each export column, and its width.
 *
 * The registry names the columns; this names the cells, so a column the
 * server adds shows up in the chooser and in the exports without the table
 * pretending to know how to render it.  The name identifies a row and stays pinned
 * when the table scrolls; Given and Net stay in sight on a phone; the rest drop, the
 * least needed first, when the table would not fit.
 */
const CELLS: Record<string, ReportCell<DonorRow>> = {
  name: {
    minWidth: '10rem',
    isIdentity: true,
    render: (row) => row.name,
    sortValue: (row) => row.name,
  },
  email: {
    minWidth: '12rem',
    dropOrder: 2,
    render: (row) => row.email,
    sortValue: (row) => row.email,
  },
  phone: {
    width: '8.5rem',
    noWrap: true,
    dropOrder: 3,
    render: (row) => row.phone,
    sortValue: (row) => row.phone,
  },
  city: { minWidth: '7rem', dropOrder: 1, render: (row) => row.city, sortValue: (row) => row.city },
  state: { width: '4rem', dropOrder: 1, render: (row) => row.state, sortValue: (row) => row.state },
  county: {
    minWidth: '7rem',
    dropOrder: 1,
    render: (row) => row.county,
    sortValue: (row) => row.county,
  },
  dart: { minWidth: '8rem', dropOrder: 1, render: (row) => row.dart, sortValue: (row) => row.dart },
  first_gift: {
    width: '7rem',
    noWrap: true,
    dropOrder: 4,
    render: (row) => <DateText value={row.first_gift} />,
    sortValue: (row) => row.first_gift ?? '',
  },
  last_gift: {
    width: '7rem',
    noWrap: true,
    dropOrder: 5,
    render: (row) => <DateText value={row.last_gift} />,
    sortValue: (row) => row.last_gift ?? '',
  },
  gifts: {
    width: '4.5rem',
    numeric: true,
    dropOrder: 4,
    render: (row) => row.gifts,
    sortValue: (row) => row.gifts,
  },
  given: {
    width: '6.5rem',
    numeric: true,
    keepInSight: true,
    render: (row) => <Money cents={row.given_cents} />,
    sortValue: (row) => row.given_cents,
  },
  refunded: {
    width: '6.5rem',
    numeric: true,
    dropOrder: 4,
    render: (row) => <Money cents={row.refunded_cents} />,
    sortValue: (row) => row.refunded_cents,
  },
  net: {
    width: '6.5rem',
    numeric: true,
    keepInSight: true,
    render: (row) => <Money cents={row.net_cents} />,
    sortValue: (row) => row.net_cents,
  },
  active: {
    width: '8.5rem',
    dropOrder: 2,
    render: (row) =>
      row.active ? (
        <StatusChip tone="current" label="Active" />
      ) : (
        <StatusChip tone="expired" label="Deactivated" />
      ),
  },
};

/**
 * The name cell for a reader who opens member records: a link to the donor's record, but
 * plain text for a "Deleted member N" row, whose record cannot be changed.
 */
const RECORD_NAME_CELL: ReportCell<DonorRow> = {
  ...CELLS.name,
  render: (row) =>
    row.is_tombstone ? row.name : <Link to={`/admin/members/${row.user_id}`}>{row.name}</Link>,
  sortValue: (row) => row.name,
};

/** The order the server lists donors in, and so the arrow the table opens on: most given. */
const DEFAULT_SORT = { key: 'net', direction: 'desc' } as const;

/**
 * The table's columns for the chosen keys, in registry order, with each name a link
 * to the donor's record when `canOpenRecords`.
 */
function tableColumns(
  registry: readonly ReportColumn[],
  chosen: readonly string[],
  canOpenRecords: boolean,
): Column<DonorRow>[] {
  const cells = canOpenRecords ? { ...CELLS, name: RECORD_NAME_CELL } : CELLS;
  return reportTableColumns(registry, chosen, cells, false);
}

/** The Donors tab of the finance area. */
export function DonorsPage(): JSX.Element {
  const [filters, setFilters] = useUrlFilters(FILTER_KEYS);
  const darts = useDarts();
  const dartOptions = useMemo(
    () => ({
      dart: (darts.data ?? []).map((dart) => ({ value: String(dart.id), label: dart.name })),
    }),
    [darts.data],
  );
  const choice = useColumnChoice('donors', FALLBACK_COLUMNS);
  // The member record is the account administrator's, so only a reader holding that
  // role as well as the treasurer's gets a link they can follow.
  const { roles } = useAuth();
  const canOpenRecords = hasAnyRole(roles, ['account_admin']);

  const rows = useDonors(filters);
  const tableCells = useMemo(
    () => tableColumns(choice.tableColumns, choice.tableChosen, canOpenRecords),
    [choice.tableColumns, choice.tableChosen, canOpenRecords],
  );
  const exportParams = { ...filters, columns: choice.chosen };

  return (
    <Page
      title="Donors"
      eyebrow="Payments"
      lede="Everyone who has given through the public donation page, and what each of them has given."
    >
      <FinanceTabs />

      <DataTable
        singleLine
        columns={tableCells}
        rows={rows.data ?? []}
        rowKey={(row) => row.user_id}
        caption="Donors"
        initialSort={DEFAULT_SORT}
        filters={
          <FilterBar
            fields={FILTER_FIELDS}
            values={filters}
            onChange={(next) => setFilters(next)}
            options={dartOptions}
            label="Filter donors"
          />
        }
        tools={<ColumnTools choice={choice} />}
        exportCsvUrl={reportExportUrl('donors', 'csv', exportParams)}
        exportPdfUrl={reportExportUrl('donors', 'pdf', exportParams)}
        isLoading={rows.isPending}
        emptyTitle="No donors match"
        emptyDescription="Try widening the date range, or reset the filters."
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
          The donors could not be loaded.
        </p>
      ) : null}
    </Page>
  );
}
