/**
 * The small inline form under the aircraft type picker that adds a type the FAA
 * has never registered, via `POST /aircraft/types`.  Only an account
 * administrator is offered it.
 *
 * It sits inside the aircraft form, and a form cannot hold another, so it is a
 * group of boxes whose **Add type** button, or Enter in any of its boxes, sends
 * the type without submitting the aircraft form around it.
 */
import { useState } from 'react';
import type { JSX, KeyboardEvent } from 'react';

import { ApiError } from '@/portal/api/client';
import type { AircraftType, AircraftTypeCreatePayload } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { maskDigits } from '@/portal/masks';
import { useCreateAircraftType } from './api';

export interface AddAircraftTypeProps {
  /** Called with the type the server added. */
  onAdded: (type: AircraftType) => void;
  onCancel: () => void;
}

interface Draft {
  make: string;
  model: string;
  seats: string;
  engines: string;
}

const EMPTY_DRAFT: Draft = { make: '', model: '', seats: '', engines: '' };

/** The make and the model are required; seats and engines are optional counts. */
function validateDraft(draft: Draft): Record<string, string> {
  const errors: Record<string, string> = {};
  if (draft.make.trim() === '') errors.make = 'Enter the make.';
  if (draft.model.trim() === '') errors.model = 'Enter the model.';
  return errors;
}

/** The request body, leaving a blank count out. */
function draftPayload(draft: Draft): AircraftTypeCreatePayload {
  return {
    make: draft.make.trim(),
    model: draft.model.trim(),
    ...(draft.seats === '' ? {} : { seats: Number(draft.seats) }),
    ...(draft.engines === '' ? {} : { engines: Number(draft.engines) }),
  };
}

/** Adds an aircraft type by hand and hands the added type to `onAdded`. */
export function AddAircraftType({
  onAdded,
  onCancel: handleCancel,
}: AddAircraftTypeProps): JSX.Element {
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const create = useCreateAircraftType();

  const set = (key: keyof Draft, value: string): void => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const handleAdd = (): void => {
    const found = validateDraft(draft);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    create.mutate(draftPayload(draft), {
      onSuccess: onAdded,
      onError: (error) => {
        if (error instanceof ApiError) setErrors(error.fieldErrors);
      },
    });
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>): void => {
    if (event.key !== 'Enter') return;
    // Enter adds the type; it must not submit the aircraft form this sits in.
    event.preventDefault();
    handleAdd();
  };

  const hasFieldError = Object.keys(errors).length > 0;

  return (
    <fieldset className="aircraft-type__add">
      <legend className="aircraft-type__legend">Add a type</legend>
      <p className="muted">For a type the FAA has never registered.</p>
      <div className="aircraft-type__grid">
        <Field label="Make" required error={errors.make}>
          {(field) => (
            <input
              {...field}
              value={draft.make}
              onChange={(event) => set('make', event.target.value)}
              onKeyDown={handleKeyDown}
            />
          )}
        </Field>
        <Field label="Model" required error={errors.model}>
          {(field) => (
            <input
              {...field}
              value={draft.model}
              onChange={(event) => set('model', event.target.value)}
              onKeyDown={handleKeyDown}
            />
          )}
        </Field>
        <Field label="Seats" error={errors.seats}>
          {(field) => (
            <MaskedInput
              {...field}
              className="num"
              inputMode="numeric"
              size={4}
              mask={(raw) => maskDigits(raw, 2)}
              value={draft.seats}
              onValueChange={(next) => set('seats', next)}
              onKeyDown={handleKeyDown}
            />
          )}
        </Field>
        <Field label="Engines" error={errors.engines}>
          {(field) => (
            <MaskedInput
              {...field}
              className="num"
              inputMode="numeric"
              size={4}
              mask={(raw) => maskDigits(raw, 1)}
              value={draft.engines}
              onValueChange={(next) => set('engines', next)}
              onKeyDown={handleKeyDown}
            />
          )}
        </Field>
      </div>
      {create.isError && !hasFieldError ? (
        <p className="field__error" role="alert">
          {create.error.message}
        </p>
      ) : null}
      <div className="cluster">
        <Button small onClick={handleAdd} disabled={create.isPending}>
          {create.isPending ? 'Adding…' : 'Add aircraft type'}
        </Button>
        <Button variant="quiet" small onClick={handleCancel}>
          Cancel
        </Button>
      </div>
    </fieldset>
  );
}
