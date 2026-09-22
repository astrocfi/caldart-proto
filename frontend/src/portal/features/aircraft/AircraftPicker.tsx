/**
 * Shared aircraft search-and-attach control.
 *
 * It searches with `GET /aircraft/lookup`, then `GET /aircraft`, and can add a
 * missing aircraft with `POST /aircraft`.  `/profile/aircraft` uses it for the
 * planes a member commonly flies.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { Aircraft } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { EmptyState } from '@/portal/components/EmptyState';
import { Field } from '@/portal/components/Field';
import { useDebounced } from '@/portal/components/useDebounced';
import './aircraft.css';
import { InsuranceChip } from './InsuranceChip';
import { ServiceChip } from './ServiceChip';
import { useAircraftSearch, useCreateAircraft } from './api';
import type { AircraftFormValues } from './form';
import { aircraftPayload, emptyAircraftValues, validateAircraft } from './form';
import { normalizeNNumber } from './insurance';

export interface AircraftPickerProps {
  onSelect: (aircraft: Aircraft) => void;
  /** Aircraft already attached, so they can be filtered out of the results. */
  excludeIds?: number[];
}

/** Search for an existing aircraft, or add one, then hand the pick to `onSelect`. */
export function AircraftPicker({ onSelect, excludeIds = [] }: AircraftPickerProps): JSX.Element {
  const [term, setTerm] = useState('');
  const [adding, setAdding] = useState(false);
  const debounced = useDebounced(term.trim());
  const search = useAircraftSearch(debounced);
  const create = useCreateAircraft();

  const found = search.data?.matches ?? [];
  const results = found.filter((aircraft) => !excludeIds.includes(aircraft.id));
  const attached = found.filter((aircraft) => excludeIds.includes(aircraft.id));
  const searched = debounced.length > 0 && search.isSuccess;
  // Offering "add a new aircraft" when the only match is already attached
  // would invite a duplicate registration; say so instead.
  const nothingToAdd = searched && results.length === 0 && attached.length === 0;

  const handleStartAdding = (): void => {
    create.reset();
    setAdding(true);
  };

  const handleCreated = (aircraft: Aircraft): void => {
    setAdding(false);
    setTerm('');
    onSelect(aircraft);
  };

  return (
    <Card eyebrow="Aircraft" title="Find an aircraft">
      <Field
        label="Search the aircraft register"
        hint="N-number, make, model or owner. Type a registration however you like — 12345, n12345 and N-12345 all match."
      >
        {(field) => (
          <input
            {...field}
            type="search"
            autoComplete="off"
            spellCheck={false}
            className="mono"
            value={term}
            placeholder="N12345"
            onChange={(event) => {
              setTerm(event.target.value);
              setAdding(false);
            }}
          />
        )}
      </Field>

      <p className="visually-hidden" role="status">
        {search.isFetching
          ? 'Searching the aircraft register'
          : searched
            ? `${results.length} aircraft found`
            : ''}
      </p>

      {search.isFetching && !search.data ? <p className="muted">Searching…</p> : null}

      {results.length > 0 ? (
        <ul className="aircraft-results">
          {results.map((aircraft) => (
            <li key={aircraft.id} className="aircraft-result">
              <button
                type="button"
                className="aircraft-result__button"
                onClick={() => onSelect(aircraft)}
              >
                <span className="aircraft-result__ident mono">{aircraft.n_number}</span>
                <span className="aircraft-result__name">
                  {aircraft.make} {aircraft.model}
                </span>
                <InsuranceChip aircraft={aircraft} />
                <ServiceChip aircraft={aircraft} />
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {attached.length > 0 ? (
        <p className="muted aircraft-attached">
          {attached.map((aircraft) => aircraft.n_number).join(', ')} already on your list.
        </p>
      ) : null}

      {nothingToAdd && !adding ? (
        <EmptyState
          title="No aircraft matches that"
          description="If the plane is not in the register yet, add it — it takes a moment."
          action={
            <Button variant="secondary" onClick={handleStartAdding}>
              Add a new aircraft
            </Button>
          }
        />
      ) : null}

      {adding ? (
        <NewAircraftForm
          nNumber={normalizeNNumber(term)}
          onCancel={() => setAdding(false)}
          onCreated={handleCreated}
          create={create}
        />
      ) : null}
    </Card>
  );
}

interface NewAircraftFormProps {
  nNumber: string;
  onCancel: () => void;
  onCreated: (aircraft: Aircraft) => void;
  create: ReturnType<typeof useCreateAircraft>;
}

/** The short form: enough to identify the plane and its insurance. */
function NewAircraftForm({
  nNumber,
  onCancel: handleCancel,
  onCreated,
  create,
}: NewAircraftFormProps) {
  const [values, setValues] = useState<AircraftFormValues>(() => emptyAircraftValues(nNumber));
  const [errors, setErrors] = useState<Record<string, string>>({});

  const set = <K extends keyof AircraftFormValues>(key: K, value: AircraftFormValues[K]): void => {
    setValues((current) => ({ ...current, [key]: value }));
  };

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    const found = validateAircraft(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    create.mutate(aircraftPayload(values), {
      onSuccess: onCreated,
      onError: (error) => {
        if (error instanceof ApiError) setErrors(error.fieldErrors);
      },
    });
  };

  return (
    <form className="aircraft-new" onSubmit={handleSubmit} noValidate>
      <h3 className="aircraft-new__title">Add an aircraft to the register</h3>

      <Field label="N-number" required error={errors.n_number}>
        {(field) => (
          <input
            {...field}
            className="mono"
            value={values.n_number}
            onChange={(event) => set('n_number', event.target.value)}
          />
        )}
      </Field>

      <div className="aircraft-new__pair">
        <Field label="Make" required error={errors.make}>
          {(field) => (
            <input
              {...field}
              value={values.make}
              placeholder="Cessna"
              onChange={(event) => set('make', event.target.value)}
            />
          )}
        </Field>
        <Field label="Model" required error={errors.model}>
          {(field) => (
            <input
              {...field}
              value={values.model}
              placeholder="172S Skyhawk"
              onChange={(event) => set('model', event.target.value)}
            />
          )}
        </Field>
      </div>

      <div className="aircraft-new__pair">
        <Field label="Year" error={errors.year}>
          {(field) => (
            <input
              {...field}
              className="mono"
              inputMode="numeric"
              value={values.year}
              onChange={(event) => set('year', event.target.value)}
            />
          )}
        </Field>
        <Field label="Owner">
          {(field) => (
            <input
              {...field}
              value={values.owner_name}
              onChange={(event) => set('owner_name', event.target.value)}
            />
          )}
        </Field>
      </div>

      <div className="aircraft-new__pair">
        <Field label="Insurance carrier">
          {(field) => (
            <input
              {...field}
              value={values.insurance_carrier}
              onChange={(event) => set('insurance_carrier', event.target.value)}
            />
          )}
        </Field>
        <Field label="Insurance expires" error={errors.insurance_expiration}>
          {(field) => (
            <input
              {...field}
              type="date"
              className="mono"
              value={values.insurance_expiration}
              onChange={(event) => set('insurance_expiration', event.target.value)}
            />
          )}
        </Field>
      </div>

      {create.isError && Object.keys(errors).length === 0 ? (
        <p className="field__error" role="alert">
          {create.error.message}
        </p>
      ) : null}

      <div className="cluster">
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? 'Adding…' : 'Add aircraft'}
        </Button>
        <Button variant="quiet" onClick={handleCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
