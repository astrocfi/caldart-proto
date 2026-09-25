/**
 * `/admin/aircraft` — the register an account administrator maintains:
 * filter, sort, export, and add a record.
 *
 * The exports carry more columns than the five the table shows, so the column
 * chooser drives the two download links rather than the table: the register
 * stays scannable while the CSV and the PDF carry whatever was asked for.
 */
import { useMemo, useState } from 'react';
import type { JSX } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { Aircraft, AircraftPatch, OwnerType } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { ColumnChooser, defaultColumnKeys } from '@/portal/components/ColumnChooser';
import { DataTable } from '@/portal/components/DataTable';
import type { Column } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { FilterBar } from '@/portal/components/FilterBar';
import { Page } from '@/portal/components/Page';
import { useToast } from '@/portal/components/Toast';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import {
  useFirstPageWhenMissing,
  useUrlListPosition,
} from '@/portal/components/useUrlListPosition';
import { AircraftForm } from '@/portal/features/aircraft/AircraftForm';
import { InsuranceDot } from '@/portal/features/aircraft/InsuranceChip';
import { ServiceChip } from '@/portal/features/aircraft/ServiceChip';
import type { AircraftFilters, InsuranceState } from '@/portal/features/aircraft/api';
import { useAircraftList, useCreateAircraft } from '@/portal/features/aircraft/api';
import { OWNER_TYPE_LABELS, emptyAircraftValues } from '@/portal/features/aircraft/form';
import { reportExportUrl, useReportColumns } from '@/portal/reports/api';
import { REPORTS, listFilters } from '@/portal/reports/definitions';
import '@/portal/features/aircraft/aircraft.css';

const PAGE_SIZE = 25;

const FILTER_FIELDS = listFilters(REPORTS.aircraft);
const FILTER_KEYS = FILTER_FIELDS.map((field) => field.key);

const DEFAULT_ORDERING = 'n_number';

/** `/admin/aircraft` page: filter, sort, export, and add aircraft register records. */
export function AircraftRegisterPage(): JSX.Element {
  const navigate = useNavigate();
  const toast = useToast();

  const [filters, setFilters] = useUrlFilters(FILTER_KEYS);
  // The order and the page live in the address beside the filters.
  const position = useUrlListPosition(DEFAULT_ORDERING);
  const { ordering, page, setPage, sort, setSort: handleSortChange } = position;
  const [adding, setAdding] = useState(false);

  const query: AircraftFilters = {
    search: filters.search,
    make: filters.make,
    owner_type: filters.owner_type as OwnerType | '',
    insurance: filters.insurance as InsuranceState | '',
    expiring_within: filters.expiring_within,
    ordering,
  };

  const list = useAircraftList({ ...query, page });
  const create = useCreateAircraft();
  useFirstPageWhenMissing(position, list.error);

  const registry = useReportColumns('aircraft');
  const reportColumns = useMemo(() => registry.data ?? [], [registry.data]);
  // Null means "whatever the registry calls default": the chooser has not been
  // touched, so it must follow a registry that is still loading.
  const [chosen, setChosen] = useState<string[] | null>(null);
  const chosenKeys = chosen ?? defaultColumnKeys(reportColumns);
  const exportParams = { ...filters, ordering, columns: chosenKeys };

  const rows = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const firstRow = count === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const lastRow = Math.min(page * PAGE_SIZE, count);

  const columns: Column<Aircraft>[] = [
    {
      key: 'n_number',
      header: 'N-number',
      width: '9rem',
      render: (row) => (
        <>
          <Link className="mono" to={`/admin/aircraft/${row.id}`}>
            {row.n_number}
          </Link>{' '}
          <ServiceChip aircraft={row} />
        </>
      ),
    },
    { key: 'make', header: 'Make', width: '16%', render: (row) => row.make },
    { key: 'model', header: 'Model', width: '16%', render: (row) => row.model },
    {
      key: 'owner_name',
      header: 'Owner',
      render: (row) => (
        <>
          {row.owner_name || '—'}
          <span className="muted"> · {OWNER_TYPE_LABELS[row.owner_type]}</span>
        </>
      ),
    },
    {
      key: 'insurance_expiration',
      header: 'Insurance',
      width: '11rem',
      render: (row) => (
        <>
          <InsuranceDot aircraft={row} /> <DateText value={row.insurance_expiration} />
        </>
      ),
    },
  ];

  const handleColumnChange = (next: string[]): void => {
    setChosen(next);
  };

  const handleSubmit = (payload: AircraftPatch): void => {
    create.mutate(payload, {
      onSuccess: (aircraft) => {
        setAdding(false);
        toast.show(`${aircraft.n_number} added to the register.`, 'success');
        void navigate(`/admin/aircraft/${aircraft.id}`);
      },
    });
  };

  const serverErrors = create.error instanceof ApiError ? create.error.fieldErrors : undefined;

  return (
    <Page
      title="Aircraft register"
      eyebrow="Administration"
      lede="Every airframe CalDART members fly, with the insurance a DART leader checks before a mission."
      actions={
        <Button
          variant={adding ? 'quiet' : 'primary'}
          onClick={() => {
            create.reset();
            setAdding((current) => !current);
          }}
        >
          {adding ? 'Close' : 'New aircraft'}
        </Button>
      }
    >
      {adding ? (
        <Card eyebrow="Register" title="Add an aircraft">
          <AircraftForm
            initial={emptyAircraftValues()}
            submitLabel="Add aircraft"
            pending={create.isPending}
            serverErrors={serverErrors}
            onSubmit={handleSubmit}
            onCancel={() => setAdding(false)}
            withAdminFields
          />
        </Card>
      ) : null}

      <DataTable
        singleLine
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        caption={`${count} aircraft`}
        isLoading={list.isPending}
        onSortChange={handleSortChange}
        sort={sort}
        exportCsvUrl={reportExportUrl('aircraft', 'csv', exportParams)}
        exportPdfUrl={reportExportUrl('aircraft', 'pdf', exportParams)}
        emptyTitle="No aircraft match these filters"
        emptyDescription="Clear a filter, or add the aircraft to the register."
        filters={
          <>
            <FilterBar
              fields={FILTER_FIELDS}
              values={filters}
              onChange={(next) => setFilters(next)}
              label="Filter aircraft"
            />
            {registry.isError ? (
              <p className="muted">
                The columns could not be loaded; the downloads carry the default columns.
              </p>
            ) : reportColumns.length > 0 ? (
              <ColumnChooser
                columns={reportColumns}
                chosen={chosenKeys}
                onChange={handleColumnChange}
                legend="Columns to export"
              />
            ) : null}
          </>
        }
      />

      {count > PAGE_SIZE ? (
        <div className="aircraft-pager">
          <Button
            variant="quiet"
            small
            disabled={!list.data?.previous}
            onClick={() => setPage(page - 1)}
          >
            ← Previous
          </Button>
          <p className="aircraft-pager__count">
            {firstRow}–{lastRow} of {count}
          </p>
          <Button
            variant="quiet"
            small
            disabled={!list.data?.next}
            onClick={() => setPage(page + 1)}
          >
            Next →
          </Button>
        </div>
      ) : null}
    </Page>
  );
}
