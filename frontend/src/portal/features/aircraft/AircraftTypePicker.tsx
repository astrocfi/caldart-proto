/**
 * The aircraft type picker: one box that searches `GET /aircraft/types` as it is
 * typed in and lists what it finds, from which the type is picked.  Picking from
 * the list is the only way to set the type, so every aircraft names one of the
 * aircraft types, and typing in the box again drops the type until another is
 * picked.
 *
 * An account administrator whose search finds nothing is offered **Add a type**,
 * for a type the FAA has never registered; the type it adds is picked at once.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { AircraftType } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { Typeahead } from '@/portal/components/Typeahead';
import { useDebounced } from '@/portal/components/useDebounced';
import { useAuth } from '@/portal/auth/useAuth';
import { hasAnyRole } from '@/portal/nav';
import { AddAircraftType } from './AddAircraftType';
import { useAircraftTypes } from './api';

/** The fewest characters worth searching the aircraft types for: `sr`, `pa`, `c1`. */
const TYPE_SEARCH_MIN_LENGTH = 2;

export interface AircraftTypePickerProps {
  /** The type picked so far, or null. */
  value: AircraftType | null;
  onChange: (type: AircraftType | null) => void;
  onBlur?: () => void;
  error?: string;
}

/** How a type reads in the box and at the start of its line in the list: make, then model. */
export function aircraftTypeName(type: AircraftType): string {
  return `${type.make} ${type.model}`;
}

/** A type's seats, for the muted end of its line in the list, or nothing when unknown. */
function seatsMeta(type: AircraftType): string {
  if (type.seats === null) return '';
  return type.seats === 1 ? '1 seat' : `${type.seats} seats`;
}

/** Search the aircraft types and pick one; an account administrator may add a missing one. */
export function AircraftTypePicker({
  value,
  onChange: handleChange,
  onBlur: handleBlur,
  error,
}: AircraftTypePickerProps): JSX.Element {
  const [text, setText] = useState(value === null ? '' : aircraftTypeName(value));
  // The type the box last showed: a type set from outside (a registration picked in
  // the N-number box) writes its
  // name into the box, while a type dropped by typing leaves the typing alone.
  const [shownId, setShownId] = useState<number | null>(value?.id ?? null);
  const [isAdding, setIsAdding] = useState(false);
  const { roles } = useAuth();
  const canAdd = hasAnyRole(roles, ['account_admin']);

  const valueId = value?.id ?? null;
  if (valueId !== shownId) {
    setShownId(valueId);
    if (value !== null) setText(aircraftTypeName(value));
  }

  const term = useDebounced(text.trim());
  const isSearching = value === null && term.length >= TYPE_SEARCH_MIN_LENGTH;
  const found = useAircraftTypes(isSearching ? term : '');
  const isNothingFound =
    isSearching && found.isSuccess && !found.isPlaceholderData && found.data.length === 0;

  const handleValueChange = (next: string): void => {
    setText(next);
    if (value !== null) handleChange(null);
  };

  const handlePick = (type: AircraftType): void => {
    setIsAdding(false);
    setText(aircraftTypeName(type));
    handleChange(type);
  };

  return (
    <div className="aircraft-type">
      <Field
        label="Aircraft type"
        required
        error={error}
        hint="Make, model, or designator: cessna 172, c172, skyhawk"
      >
        {(field) => (
          <Typeahead
            {...field}
            listLabel="Aircraft types"
            value={text}
            onValueChange={handleValueChange}
            onPick={handlePick}
            onBlur={handleBlur}
            useSuggestions={useAircraftTypes}
            itemKey={(type) => String(type.id)}
            itemLabel={aircraftTypeName}
            itemMeta={seatsMeta}
            minLength={TYPE_SEARCH_MIN_LENGTH}
            autoComplete="off"
          />
        )}
      </Field>
      {isNothingFound && !isAdding ? (
        <p className="cluster aircraft-type__none">
          <span className="muted">No aircraft type matches that.</span>
          {canAdd ? (
            <Button
              variant="secondary"
              small
              // Leaving the box marks it with its error, which pushes this button
              // down under the pointer, so the press keeps the focus where it is.
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => setIsAdding(true)}
            >
              Add a type
            </Button>
          ) : null}
        </p>
      ) : null}
      {canAdd && isAdding ? (
        <AddAircraftType onAdded={handlePick} onCancel={() => setIsAdding(false)} />
      ) : null}
    </div>
  );
}
