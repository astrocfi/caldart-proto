/**
 * `/admin/payments/contributions` — the year-end acknowledgment list.
 *
 * One row per member who gave something in the chosen calendar year, largest
 * net giver first, with the statement each of them can be sent.  The net
 * figure is the one an acknowledgment letter quotes, so it is the column the
 * table leads the eye to.
 */
import type { JSX } from 'react';

import type { ContributionRow } from '@/portal/api/types';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { FilterBar } from '@/portal/components/FilterBar';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import { reportExportUrl } from '@/portal/reports/api';
import { REPORTS, listFilters } from '@/portal/reports/definitions';
import { statementUrl } from './api';
import { FinanceTabs } from './FinanceTabs';
import { useContributions } from './reports-api';
import './admin-payments.css';

const FILTER_FIELDS = listFilters(REPORTS.contributions);
const FILTER_KEYS = FILTER_FIELDS.map((field) => field.key);

/** The years the Year field offers; blank, its first choice, is this year. */
const OFFERED_YEARS = new Set(
  (FILTER_FIELDS.find((field) => field.key === 'year')?.options ?? []).map(
    (option) => option.value,
  ),
);

function columns(year: number): Column<ContributionRow>[] {
  return [
    { key: 'name', header: 'Member', render: (row) => row.name, sortValue: (row) => row.name },
    { key: 'email', header: 'Email', render: (row) => row.email, sortValue: (row) => row.email },
    {
      key: 'count',
      header: 'Payments',
      numeric: true,
      render: (row) => row.count,
      sortValue: (row) => row.count,
    },
    {
      key: 'contribution_cents',
      header: 'Given',
      numeric: true,
      render: (row) => <Money cents={row.contribution_cents} />,
      sortValue: (row) => row.contribution_cents,
    },
    {
      key: 'refunded_cents',
      header: 'Refunded',
      numeric: true,
      render: (row) => <Money cents={row.refunded_cents} />,
      sortValue: (row) => row.refunded_cents,
    },
    {
      key: 'net_contribution_cents',
      header: 'Net',
      numeric: true,
      render: (row) => <Money cents={row.net_contribution_cents} />,
      sortValue: (row) => row.net_contribution_cents,
    },
    {
      key: 'statement',
      header: 'Statement',
      sortable: false,
      render: (row) => (
        <a href={statementUrl(row.user_id, year)} className="button button--quiet button--small">
          Statement
        </a>
      ),
    },
  ];
}

/** The Contributions tab of the finance area. */
export function ContributionsPage(): JSX.Element {
  const [addressFilters, setFilters] = useUrlFilters(FILTER_KEYS);
  // A year the Year field does not offer reads as blank, so the select, the
  // rows, the caption and the downloads never disagree about the year shown.
  const filters = OFFERED_YEARS.has(addressFilters.year ?? '')
    ? addressFilters
    : { ...addressFilters, year: '' };
  // A blank year is the current one, which the server reports on by default;
  // the statements and the caption need it spelled out.
  const year = Number(filters.year) || new Date().getFullYear();

  const rows = useContributions(filters.year ?? '');

  return (
    <Page
      title="Contributions"
      eyebrow="Payments"
      lede="Everyone who gave in one calendar year, and what each of them gave."
    >
      <FinanceTabs />

      <p className="muted">
        A payment counts in the year its money arrived. The net figure is what an acknowledgment
        letter quotes: given, less anything refunded against it.
      </p>

      <DataTable
        columns={columns(year)}
        rows={rows.data ?? []}
        rowKey={(row) => row.user_id}
        caption={`Contributions in ${year}`}
        filters={
          <FilterBar
            fields={FILTER_FIELDS}
            values={filters}
            onChange={(next) => setFilters(next)}
            label="Filter contributions"
          />
        }
        exportCsvUrl={reportExportUrl('contributions', 'csv', filters)}
        exportPdfUrl={reportExportUrl('contributions', 'pdf', filters)}
        isLoading={rows.isPending}
        emptyTitle="No contributions that year"
        emptyDescription="Choose another year, or check that the payments were recorded."
      />

      {rows.isError ? (
        <p role="alert" className="field__error">
          The contributions could not be loaded.
        </p>
      ) : null}
    </Page>
  );
}
