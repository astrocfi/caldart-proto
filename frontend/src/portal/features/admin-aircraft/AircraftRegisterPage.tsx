/**
 * `/admin/aircraft` — the register an account administrator maintains:
 * filter, sort, export, and add a record.
 */
import { useState } from 'react';
import type { JSX } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { Aircraft, AircraftPatch } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { DataTable } from '@/portal/components/DataTable';
import type { Column, SortDirection } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { Page } from '@/portal/components/Page';
import { useToast } from '@/portal/components/Toast';
import { useDebounced } from '@/portal/components/useDebounced';
import { AircraftForm } from '@/portal/features/aircraft/AircraftForm';
import { InsuranceChip } from '@/portal/features/aircraft/InsuranceChip';
import { ServiceChip } from '@/portal/features/aircraft/ServiceChip';
import type { AircraftFilters } from '@/portal/features/aircraft/api';
import {
  aircraftExportUrl,
  useAircraftList,
  useCreateAircraft,
} from '@/portal/features/aircraft/api';
import {
  OWNER_TYPES,
  OWNER_TYPE_LABELS,
  emptyAircraftValues,
} from '@/portal/features/aircraft/form';
import '@/portal/features/aircraft/aircraft.css';

const PAGE_SIZE = 25;

const INSURANCE_OPTIONS = [
  { value: '', label: 'Any insurance state' },
  { value: 'current', label: 'Insured' },
  { value: 'expired', label: 'Expired' },
  { value: 'missing', label: 'Not on file' },
] as const;

const EXPIRING_OPTIONS = [
  { value: '', label: 'Any expiry' },
  { value: '30', label: 'Expiring in 30 days' },
  { value: '60', label: 'Expiring in 60 days' },
  { value: '90', label: 'Expiring in 90 days' },
] as const;

/** DataTable reports a column key; the API wants an `ordering` term. */
export function orderingFor(key: string, direction: SortDirection): string {
  return direction === 'desc' ? `-${key}` : key;
}

/** `/admin/aircraft` page: filter, sort, export and add aircraft register records. */
export function AircraftRegisterPage(): JSX.Element {
  const navigate = useNavigate();
  const toast = useToast();

  const [search, setSearch] = useState('');
  const [make, setMake] = useState('');
  const [ownerType, setOwnerType] = useState('');
  const [insurance, setInsurance] = useState('');
  const [expiring, setExpiring] = useState('');
  const [ordering, setOrdering] = useState('n_number');
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState(false);

  const debouncedSearch = useDebounced(search.trim());
  const debouncedMake = useDebounced(make.trim());

  const filters: AircraftFilters = {
    search: debouncedSearch,
    make: debouncedMake,
    owner_type: ownerType as AircraftFilters['owner_type'],
    insurance: insurance as AircraftFilters['insurance'],
    expiring_within: expiring,
    ordering,
  };

  const list = useAircraftList({ ...filters, page });
  const create = useCreateAircraft();

  const reset = (change: () => void): void => {
    change();
    setPage(1);
  };

  const rows = list.data?.results ?? [];
  const count = list.data?.count ?? 0;
  const firstRow = count === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const lastRow = Math.min(page * PAGE_SIZE, count);

  const columns: Column<Aircraft>[] = [
    {
      key: 'n_number',
      header: 'N-number',
      render: (row) => (
        <span className="cluster">
          <Link className="mono" to={`/admin/aircraft/${row.id}`}>
            {row.n_number}
          </Link>
          <ServiceChip aircraft={row} />
        </span>
      ),
    },
    { key: 'make', header: 'Make', render: (row) => row.make },
    { key: 'model', header: 'Model', render: (row) => row.model },
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
      render: (row) => (
        <span className="cluster">
          <InsuranceChip aircraft={row} />
          <DateText value={row.insurance_expiration} />
        </span>
      ),
    },
  ];

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
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        caption={`${count} aircraft`}
        isLoading={list.isPending}
        onSortChange={(key, direction) => reset(() => setOrdering(orderingFor(key, direction)))}
        initialSort={{ key: 'n_number', direction: 'asc' }}
        exportCsvUrl={aircraftExportUrl('csv', filters)}
        exportPdfUrl={aircraftExportUrl('pdf', filters)}
        emptyTitle="No aircraft match these filters"
        emptyDescription="Clear a filter, or add the aircraft to the register."
        filters={
          <div className="aircraft-filters">
            <Field label="Search" hint="N-number, make, model or owner.">
              {(field) => (
                <input
                  {...field}
                  type="search"
                  value={search}
                  onChange={(event) => reset(() => setSearch(event.target.value))}
                />
              )}
            </Field>
            <Field label="Make">
              {(field) => (
                <input
                  {...field}
                  type="search"
                  value={make}
                  onChange={(event) => reset(() => setMake(event.target.value))}
                />
              )}
            </Field>
            <Field label="Owner type">
              {(field) => (
                <select
                  {...field}
                  value={ownerType}
                  onChange={(event) => reset(() => setOwnerType(event.target.value))}
                >
                  <option value="">Any owner type</option>
                  {OWNER_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {OWNER_TYPE_LABELS[type]}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label="Insurance">
              {(field) => (
                <select
                  {...field}
                  value={insurance}
                  onChange={(event) => reset(() => setInsurance(event.target.value))}
                >
                  {INSURANCE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label="Expiring within">
              {(field) => (
                <select
                  {...field}
                  value={expiring}
                  onChange={(event) => reset(() => setExpiring(event.target.value))}
                >
                  {EXPIRING_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              )}
            </Field>
          </div>
        }
      />

      {count > PAGE_SIZE ? (
        <div className="aircraft-pager">
          <Button
            variant="quiet"
            small
            disabled={!list.data?.previous}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
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
            onClick={() => setPage((current) => current + 1)}
          >
            Next →
          </Button>
        </div>
      ) : null}
    </Page>
  );
}
