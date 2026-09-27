/**
 * The aircraft type picker: a search box over `GET /aircraft/types` and the
 * list it fills, from which the type is picked.  Picking from the list is the
 * only way to set the type, so every aircraft names one of the aircraft types.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { AircraftType } from '@/portal/api/types';
import { Field } from '@/portal/components/Field';
import { useDebounced } from '@/portal/components/useDebounced';
import { useAircraftTypes } from './api';

export interface AircraftTypeSelectProps {
  /** The type picked so far, or null. */
  value: AircraftType | null;
  onChange: (type: AircraftType | null) => void;
  onBlur?: () => void;
  error?: string;
}

/** How one type reads in the list: its make and model, then its seats when known. */
export function aircraftTypeLabel(type: AircraftType): string {
  const name = `${type.make} ${type.model}`;
  return type.seats === null ? name : `${name} · ${type.seats} seats`;
}

/** Search for an aircraft type, then pick it from the list the search fills. */
export function AircraftTypeSelect({
  value,
  onChange: handleChange,
  onBlur: handleBlur,
  error,
}: AircraftTypeSelectProps): JSX.Element {
  const [term, setTerm] = useState('');
  const found = useAircraftTypes(useDebounced(term.trim()));
  const results = found.data ?? [];
  // The picked type stays on offer while a new search shows other ones.
  const options =
    value === null || results.some((type) => type.id === value.id) ? results : [value, ...results];

  const handlePick = (id: string): void => {
    handleChange(options.find((type) => String(type.id) === id) ?? null);
  };

  return (
    <>
      <Field label="Find the aircraft type" hint="Make, model, or designator: cessna 172, c172">
        {(field) => (
          <input
            {...field}
            type="search"
            value={term}
            onChange={(event) => setTerm(event.target.value)}
          />
        )}
      </Field>
      <Field label="Aircraft type" required error={error}>
        {(field) => (
          <select
            {...field}
            value={value === null ? '' : String(value.id)}
            onChange={(event) => handlePick(event.target.value)}
            onBlur={handleBlur}
          >
            <option value="">
              {options.length === 0 ? 'Search for the type first' : 'Pick the type'}
            </option>
            {options.map((type) => (
              <option key={type.id} value={type.id}>
                {aircraftTypeLabel(type)}
              </option>
            ))}
          </select>
        )}
      </Field>
    </>
  );
}
