/**
 * `/admin/payments/donors` — everyone who has given through the public
 * donation page, for the treasurer alone.
 *
 * One row per donor, aggregated over the range the filter bar narrows to:
 * how much they have given, how much of it came back, and when they last
 * gave.  An account administrator does not reach this screen; the route
 * guard and `FinanceTabs` both key off the treasurer role.  The column
 * chooser drives the table and both exports at once, so what a treasurer
 * sees is what the downloaded file holds, as `PaymentsListPage` does.
 */
import { useMemo, useState } from 'react';
import type { JSX } from 'react';

import type { DonorRow, ReportColumn } from '@/portal/api/types';
import { useDarts } from '@/portal/api/queries';
import { ColumnChooser, defaultColumnKeys } from '@/portal/components/ColumnChooser';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { FilterBar } from '@/portal/components/FilterBar';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { StatusChip } from '@/portal/components/StatusChip';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import { reportExportUrl, useReportColumns } from '@/portal/reports/api';
import { REPORTS, listFilters } from '@/portal/reports/definitions';
import { useDonors } from './api';
import { FinanceTabs } from './FinanceTabs';
import './admin-payments.css';

const FILTER_FIELDS = listFilters(REPORTS.donors);
const FILTER_KEYS = FILTER_FIELDS.map((field) => field.key);

/**
 * How the table draws each export column.
 *
 * The registry names the columns; this names the cells, so a column the
 * server adds shows up in the chooser and in the exports without the table
 * pretending to know how to render it.
 */
const CELLS: Record<string, Omit<Column<DonorRow>, 'key' | 'header'>> = {
  name: { render: (row) => row.name, sortValue: (row) => row.name },
  email: { render: (row) => row.email, sortValue: (row) => row.email },
  phone: { render: (row) => row.phone, sortValue: (row) => row.phone },
  city: { render: (row) => row.city, sortValue: (row) => row.city },
  state: { render: (row) => row.state, sortValue: (row) => row.state },
  county: { render: (row) => row.county, sortValue: (row) => row.county },
  dart: { render: (row) => row.dart, sortValue: (row) => row.dart },
  first_gift: {
    render: (row) => <DateText value={row.first_gift} />,
    sortValue: (row) => row.first_gift ?? '',
  },
  last_gift: {
    render: (row) => <DateText value={row.last_gift} />,
    sortValue: (row) => row.last_gift ?? '',
  },
  gifts: {
    numeric: true,
    render: (row) => row.gifts,
    sortValue: (row) => row.gifts,
  },
  given: {
    numeric: true,
    render: (row) => <Money cents={row.given_cents} />,
    sortValue: (row) => row.given_cents,
  },
  refunded: {
    numeric: true,
    render: (row) => <Money cents={row.refunded_cents} />,
    sortValue: (row) => row.refunded_cents,
  },
  net: {
    numeric: true,
    render: (row) => <Money cents={row.net_cents} />,
    sortValue: (row) => row.net_cents,
  },
  active: {
    render: (row) =>
      row.active ? (
        <StatusChip tone="current" label="Active" />
      ) : (
        <StatusChip tone="expired" label="Deactivated" />
      ),
  },
};

/** The table's columns for the chosen keys, in registry order. */
function tableColumns(registry: ReportColumn[], chosen: string[]): Column<DonorRow>[] {
  return registry
    .filter((column) => chosen.includes(column.key))
    .map((column) => {
      const cell = CELLS[column.key] ?? { render: () => '—' };
      return { ...cell, key: column.key, header: column.label };
    });
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
  const [chosen, setChosen] = useState<string[] | null>(null);

  const registry = useReportColumns('donors');
  const columns = useMemo(() => registry.data ?? [], [registry.data]);
  const chosenKeys = chosen ?? defaultColumnKeys(columns);

  const rows = useDonors(filters);
  const tableCells = useMemo(() => tableColumns(columns, chosenKeys), [columns, chosenKeys]);
  const exportParams = { ...filters, columns: chosenKeys };

  function handleColumnChange(next: string[]) {
    setChosen(next);
  }

  return (
    <Page
      title="Donors"
      eyebrow="Payments"
      lede="Everyone who has given through the public donation page, and what each of them has given."
    >
      <FinanceTabs />

      <DataTable
        columns={tableCells}
        rows={rows.data ?? []}
        rowKey={(row) => row.user_id}
        caption="Donors"
        filters={
          <>
            <FilterBar
              fields={FILTER_FIELDS}
              values={filters}
              onChange={(next) => setFilters(next)}
              options={dartOptions}
              label="Filter donors"
            />
            {registry.isError ? (
              <p className="muted">
                The columns could not be loaded; the downloads carry the default columns.
              </p>
            ) : columns.length > 0 ? (
              <ColumnChooser
                report="donors"
                columns={columns}
                chosen={chosenKeys}
                onChange={handleColumnChange}
              />
            ) : null}
          </>
        }
        exportCsvUrl={reportExportUrl('donors', 'csv', exportParams)}
        exportPdfUrl={reportExportUrl('donors', 'pdf', exportParams)}
        isLoading={rows.isPending}
        emptyTitle="No donors match"
        emptyDescription="Try widening the date range or clearing a filter."
      />

      {rows.isError ? (
        <p role="alert" className="field__error">
          The donors could not be loaded.
        </p>
      ) : null}
    </Page>
  );
}
