/**
 * `/admin/payments/contributions` — the year-end acknowledgment list.
 *
 * One row per member who gave something in the chosen calendar year, largest
 * net giver first, with the statement each of them can be sent.  The net
 * figure is the one an acknowledgment letter quotes, so it is the column the
 * table leads the eye to.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { ContributionRow } from '@/portal/api/types';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { Field } from '@/portal/components/Field';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import { FinanceTabs } from './FinanceTabs';
import { contributionsExportUrl, statementUrl, useContributions } from './reports-api';
import './admin-payments.css';

/** How many years back the chooser offers, counting the current one. */
export const YEARS_OFFERED = 10;

/** The years the chooser lists, this year first. */
export function offeredYears(today: Date = new Date()): number[] {
  const thisYear = today.getFullYear();
  return Array.from({ length: YEARS_OFFERED }, (_unused, back) => thisYear - back);
}

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
  const years = offeredYears();
  const [year, setYear] = useState<number>(years[0] ?? new Date().getFullYear());

  const rows = useContributions(year);

  const filterBar = (
    <div className="payment-filters">
      <Field label="Year">
        {(props) => (
          <select
            {...props}
            value={String(year)}
            onChange={(event) => setYear(Number(event.target.value))}
          >
            {years.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        )}
      </Field>
    </div>
  );

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
        filters={filterBar}
        exportCsvUrl={contributionsExportUrl(year, 'csv')}
        exportPdfUrl={contributionsExportUrl(year, 'pdf')}
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
