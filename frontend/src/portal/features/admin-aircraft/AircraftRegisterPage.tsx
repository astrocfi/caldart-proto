/**
 * `/admin/aircraft` — the register an account administrator maintains:
 * filter, sort, export, and add a record.  A system administrator also sees the
 * coverage policy that says which aircraft CalDART's insurance does not cover.  The header says which day the FAA
 * registry behind the N-number box and the aircraft types was imported.
 *
 * The column chooser governs the table and the two downloads together: the table
 * shows the aircraft report's chosen columns, in the report's order, and a saved set
 * applies to the screen as it does to the files.  N-number, Make, Model, Owner, and
 * Expires sort on the server; the other headings do not sort.  On a narrow screen the
 * optional columns go first, and the N-number and the insurance expiry stay.  The
 * Pilots column is in the downloads alone: the register is open to every member, and
 * who flies an aircraft is the member check's to show, so the table draws a dash.
 */
import { useCallback, useMemo, useState } from 'react';
import type { JSX } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type {
  Aircraft,
  AircraftCategory,
  AircraftPatch,
  Airworthiness,
  OwnerType,
  ReportColumn,
} from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DataTable } from '@/portal/components/DataTable';
import { formatDate } from '@/portal/components/DateText';
import { FilterBar, clearedValues } from '@/portal/components/FilterBar';
import { Money } from '@/portal/components/Money';
import { Page } from '@/portal/components/Page';
import type { ReportCell } from '@/portal/components/reportTable';
import { ColumnTools, reportTableColumns, useColumnChoice } from '@/portal/components/reportTable';
import { useToast } from '@/portal/components/Toast';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import {
  useFirstPageWhenMissing,
  useUrlListPosition,
} from '@/portal/components/useUrlListPosition';
import { usePanelFocus } from '@/portal/components/focus';
import { useRegistryStatus } from '@/portal/api/queries';
import { useAuth } from '@/portal/auth/useAuth';
import type { RegistryStatus } from '@/portal/api/types';
import { AircraftForm } from '@/portal/features/aircraft/AircraftForm';
import { AIRWORTHINESS_LABELS, CATEGORY_LABELS } from '@/portal/features/aircraft/categories';
import { InsuranceDot } from '@/portal/features/aircraft/InsuranceDot';
import { ServiceDot } from '@/portal/features/aircraft/ServiceDot';
import type { AircraftFilters, InsuranceState } from '@/portal/features/aircraft/api';
import { useAircraftList, useCreateAircraft } from '@/portal/features/aircraft/api';
import { OWNER_TYPE_LABELS, emptyAircraftValues } from '@/portal/features/aircraft/form';
import { hasAnyRole } from '@/portal/nav';
import { reportExportUrl } from '@/portal/reports/api';
import { REPORTS, listFilters } from '@/portal/reports/definitions';
import '@/portal/features/aircraft/aircraft.css';
import { CoveragePolicyCard } from './CoveragePolicyCard';

const PAGE_SIZE = 25;

const FILTER_FIELDS = listFilters(REPORTS.aircraft);
const FILTER_KEYS = FILTER_FIELDS.map((field) => field.key);

const DEFAULT_ORDERING = 'n_number';

/** The header's line about the FAA registry: the day of its newest successful import. */
function registryLine({ as_of: asOf }: RegistryStatus): string {
  return asOf === null ? 'FAA data not loaded yet' : `FAA data as of ${formatDate(asOf)}`;
}

/** A column that only somebody who asks for it sees, and that goes first on a narrow screen. */
const OPTIONAL = 1;

/**
 * How each aircraft report column draws.  The optional columns go first on a narrow
 * screen, then the insurance figures, then the owner, model, and make; the N-number
 * and the insurance expiry stay.
 */
const CELLS: Record<string, ReportCell<Aircraft>> = {
  n_number: {
    ordering: 'n_number',
    isIdentity: true,
    width: '9rem',
    render: (row) => (
      <>
        <Link className="num" to={`/admin/aircraft/${row.id}`}>
          {row.n_number}
        </Link>{' '}
        <ServiceDot aircraft={row} />
      </>
    ),
  },
  make: { ordering: 'make', minWidth: '8rem', dropOrder: 10, render: (row) => row.make },
  model: { ordering: 'model', minWidth: '8rem', dropOrder: 11, render: (row) => row.model },
  category: {
    width: '8rem',
    dropOrder: OPTIONAL,
    render: (row) => (row.category === '' ? '' : CATEGORY_LABELS[row.category]),
  },
  airworthiness: {
    width: '9rem',
    dropOrder: OPTIONAL,
    render: (row) => (row.airworthiness === '' ? '' : AIRWORTHINESS_LABELS[row.airworthiness]),
  },
  owner_name: {
    ordering: 'owner_name',
    minWidth: '12rem',
    dropOrder: 12,
    render: (row) => row.owner_name || '—',
  },
  owner_type: {
    width: '8rem',
    dropOrder: OPTIONAL,
    render: (row) => OWNER_TYPE_LABELS[row.owner_type],
  },
  insurance_carrier: {
    minWidth: '9rem',
    dropOrder: 5,
    render: (row) => row.insurance_carrier,
  },
  liability_per_occurrence: {
    numeric: true,
    width: '10rem',
    dropOrder: 3,
    render: (row) => <Money cents={row.insurance_liability_per_occurrence_cents} whole />,
  },
  liability_per_person: {
    numeric: true,
    width: '9rem',
    dropOrder: OPTIONAL,
    render: (row) => <Money cents={row.insurance_liability_per_person_cents} whole />,
  },
  hull: {
    numeric: true,
    width: '7.5rem',
    dropOrder: 4,
    render: (row) => <Money cents={row.insurance_hull_cents} whole />,
  },
  insurance_expiration: {
    ordering: 'insurance_expiration',
    width: '12rem',
    keepInSight: true,
    render: (row) => <InsuranceDot aircraft={row} withDate />,
  },
  insurance_current: {
    width: '6.5rem',
    dropOrder: 6,
    render: (row) => (row.insurance_is_current ? 'Yes' : 'No'),
  },
  // Who flies an aircraft is the member check's to show; the downloads carry it.
  pilots: { width: '8rem', dropOrder: OPTIONAL, render: () => '—' },
};

/**
 * The report's default columns, which the table shows while the registry loads or if it
 * cannot be read, so the table and the downloads still agree.
 */
const FALLBACK_COLUMNS: ReportColumn[] = [
  { key: 'n_number', label: 'N-number', default: true },
  { key: 'make', label: 'Make', default: true },
  { key: 'model', label: 'Model', default: true },
  { key: 'owner_name', label: 'Owner', default: true },
  { key: 'insurance_carrier', label: 'Carrier', default: true },
  { key: 'liability_per_occurrence', label: 'Liability / occurrence', default: true },
  { key: 'hull', label: 'Hull', default: true },
  { key: 'insurance_expiration', label: 'Expires', default: true },
  { key: 'insurance_current', label: 'Current', default: true },
];

/** `/admin/aircraft` page: filter, sort, export, and add aircraft register records. */
export function AircraftRegisterPage(): JSX.Element {
  const navigate = useNavigate();
  const toast = useToast();
  const { roles } = useAuth();
  const isSystemAdmin = hasAnyRole(roles, ['system_admin']);

  const [filters, setFilters] = useUrlFilters(FILTER_KEYS);
  // The order and the page live in the address beside the filters.
  const position = useUrlListPosition(DEFAULT_ORDERING);
  const { ordering, page, setPage, sort, setSort: handleSortChange } = position;
  const [adding, setAdding] = useState(false);
  const handleStopAdding = useCallback(() => setAdding(false), []);
  const addFormRef = usePanelFocus(adding ? 'add' : null, handleStopAdding);

  const query: AircraftFilters = {
    search: filters.search,
    make: filters.make,
    category: filters.category as AircraftCategory | '',
    airworthiness: filters.airworthiness as Airworthiness | '',
    owner_type: filters.owner_type as OwnerType | '',
    insurance: filters.insurance as InsuranceState | '',
    expiring_within: filters.expiring_within,
    ordering,
  };

  const list = useAircraftList({ ...query, page });
  const create = useCreateAircraft();
  const registryStatus = useRegistryStatus();
  useFirstPageWhenMissing(position, list.error);

  const choice = useColumnChoice('aircraft', FALLBACK_COLUMNS);
  const columns = useMemo(
    () => reportTableColumns(choice.tableColumns, choice.tableChosen, CELLS, true),
    [choice.tableColumns, choice.tableChosen],
  );
  const exportParams = { ...filters, ordering, columns: choice.chosen };

  const rows = list.data?.results ?? [];
  const count = list.data?.count ?? 0;

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
      lede="Every airframe CalDART members fly, with the insurance a DART leader checks before a mission."
      actions={
        <>
          {registryStatus.data === undefined ? null : (
            <span className="muted aircraft-registry-date">
              {registryLine(registryStatus.data)}
            </span>
          )}
          <Button
            variant={adding ? 'quiet' : 'primary'}
            onClick={() => {
              create.reset();
              setAdding((current) => !current);
            }}
          >
            {adding ? 'Close' : 'New aircraft'}
          </Button>
        </>
      }
    >
      {adding ? (
        <div ref={addFormRef}>
          <Card eyebrow="Register" title="Add an aircraft">
            <AircraftForm
              initial={emptyAircraftValues()}
              submitLabel="Add aircraft"
              pending={create.isPending}
              serverErrors={serverErrors}
              serverError={create.error}
              onSubmit={handleSubmit}
              onCancel={handleStopAdding}
              withAdminFields
            />
          </Card>
        </div>
      ) : null}

      {isSystemAdmin ? <CoveragePolicyCard /> : null}

      <DataTable
        singleLine
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        caption={`${count} aircraft`}
        label="Aircraft register"
        isLoading={list.isPending}
        onSortChange={handleSortChange}
        sort={sort}
        exportCsvUrl={reportExportUrl('aircraft', 'csv', exportParams)}
        exportPdfUrl={reportExportUrl('aircraft', 'pdf', exportParams)}
        emptyTitle="No aircraft match these filters"
        emptyDescription="Reset the filters, or add the aircraft to the register."
        emptyAction={
          <Button variant="quiet" onClick={() => setFilters(clearedValues(FILTER_FIELDS, filters))}>
            Reset filters
          </Button>
        }
        filters={
          <FilterBar
            fields={FILTER_FIELDS}
            values={filters}
            onChange={(next) => setFilters(next)}
            label="Filter aircraft"
          />
        }
        tools={<ColumnTools choice={choice} />}
        pagination={{
          page,
          pageSize: PAGE_SIZE,
          count,
          onPageChange: setPage,
          label: 'Aircraft pages',
        }}
      />
    </Page>
  );
}
