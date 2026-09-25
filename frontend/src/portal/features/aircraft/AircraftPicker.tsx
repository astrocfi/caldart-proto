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
import { MaskedInput } from '@/portal/components/MaskedInput';
import { useDebounced } from '@/portal/components/useDebounced';
import { maskDigits, maskNNumber } from '@/portal/masks';
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
  // Say so when a search found nothing, rather than leaving the results blank.
  const nothingFound = searched && results.length === 0 && attached.length === 0;

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
        hint="N-number, make, model, or owner. Type a registration however you like — 12345, n12345, and N-12345 all match."
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
        <>
          <p className="muted aircraft-pick">Click on an aircraft to add it to your list.</p>
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
        </>
      ) : null}

      {nothingFound && !adding ? (
        <EmptyState
          title="No aircraft matches that"
          description="If the plane is not in the register yet, add it below."
        />
      ) : null}

      {attached.length > 0 ? (
        <p className="muted aircraft-attached">
          {joinNNumbers(attached.map((aircraft) => aircraft.n_number))}{' '}
          {attached.length === 1 ? 'is' : 'are'} already on your list.
        </p>
      ) : null}

      {adding ? null : (
        <p className="cluster aircraft-add">
          <Button variant="secondary" onClick={handleStartAdding}>
            Add a new aircraft
          </Button>
          <span className="muted">Not in the register? Add it yourself.</span>
        </p>
      )}

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

/**
 * Join registrations into a phrase: one alone, two with `and`, more with commas
 * and a serial comma before the final `and`.
 */
function joinNNumbers(nNumbers: string[]): string {
  if (nNumbers.length < 3) return nNumbers.join(' and ');
  return `${nNumbers.slice(0, -1).join(', ')}, and ${nNumbers.at(-1)}`;
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
          <MaskedInput
            {...field}
            className="mono"
            placeholder="N172SP"
            mask={maskNNumber}
            value={values.n_number}
            onValueChange={(next) => set('n_number', next)}
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
            <MaskedInput
              {...field}
              className="mono"
              inputMode="numeric"
              mask={(raw) => maskDigits(raw, 4)}
              value={values.year}
              onValueChange={(next) => set('year', next)}
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
