/**
 * Shared aircraft search-and-attach control.
 *
 * It searches with `GET /aircraft/lookup`, then `GET /aircraft`, and can add a
 * missing aircraft with `POST /aircraft` through the full `<AircraftForm/>`, whose
 * N-number box offers the FAA registry's registrations as it is typed into.
 * `/profile/aircraft` uses it for the planes a member commonly flies.
 */
import { useCallback, useId, useRef, useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { Aircraft } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { EmptyState } from '@/portal/components/EmptyState';
import { Field } from '@/portal/components/Field';
import { useDebounced } from '@/portal/components/useDebounced';
import { usePanelFocus } from '@/portal/components/focus';
import { AircraftForm } from './AircraftForm';
import './aircraft.css';
import { InsuranceChip } from './InsuranceChip';
import { ServiceChip } from './ServiceChip';
import { useAircraftSearch, useCreateAircraft } from './api';
import { emptyAircraftValues } from './form';
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
  const addTitleId = useId();
  const fieldErrors = create.error instanceof ApiError ? create.error.fieldErrors : undefined;

  const found = search.data?.matches ?? [];
  const results = found.filter((aircraft) => !excludeIds.includes(aircraft.id));
  const attached = found.filter((aircraft) => excludeIds.includes(aircraft.id));
  const searched = debounced.length > 0 && search.isSuccess;
  // Say so when a search found nothing, rather than leaving the results blank.
  const nothingFound = searched && results.length === 0 && attached.length === 0;

  // The add form takes the place of its button, which gets the focus back as it closes.
  const addRef = useRef<HTMLButtonElement>(null);
  const handleStopAdding = useCallback(() => setAdding(false), []);
  const addFormRef = usePanelFocus<HTMLElement>(adding ? 'add' : null, handleStopAdding, addRef);

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
          <Button ref={addRef} variant="secondary" onClick={handleStartAdding}>
            Add a new aircraft
          </Button>
          <span className="muted">Not in the register? Add it yourself.</span>
        </p>
      )}

      {adding ? (
        <section ref={addFormRef} className="aircraft-new" aria-labelledby={addTitleId}>
          <h3 id={addTitleId} className="aircraft-new__title">
            Add an aircraft to the register
          </h3>
          <AircraftForm
            initial={emptyAircraftValues(normalizeNNumber(term))}
            submitLabel="Add aircraft"
            pending={create.isPending}
            serverErrors={fieldErrors}
            serverError={create.error}
            onSubmit={(payload) => create.mutate(payload, { onSuccess: handleCreated })}
            onCancel={handleStopAdding}
          />
          {create.isError && Object.keys(fieldErrors ?? {}).length === 0 ? (
            <p className="field__error" role="alert">
              {create.error.message}
            </p>
          ) : null}
        </section>
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
