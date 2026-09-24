/**
 * The full aircraft record, in four sections: the airframe, its owner, its
 * insurance and the administrator's own notes.
 */
import { useId, useState } from 'react';
import type { JSX } from 'react';

import type { AircraftPatch } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { maskDigits, maskDollars, maskNNumber } from '@/portal/masks';
import './aircraft.css';
import { matchType, suggestTypes } from './catalog';
import type { AircraftFormValues } from './form';
import { OWNER_TYPES, OWNER_TYPE_LABELS, aircraftPayload, validateAircraft } from './form';

export interface AircraftFormProps {
  initial: AircraftFormValues;
  submitLabel: string;
  pending?: boolean;
  /** Field errors returned by the serializer, merged with the local ones. */
  serverErrors?: Record<string, string>;
  onSubmit: (payload: AircraftPatch) => void;
  onCancel?: () => void;
  /** Notes and the active flag: only on the administrator's screen. */
  withAdminFields?: boolean;
}

/** The aircraft record form, shared by the create and edit screens. */
export function AircraftForm({
  initial,
  submitLabel,
  pending = false,
  serverErrors,
  onSubmit,
  onCancel: handleCancel,
  withAdminFields = false,
}: AircraftFormProps): JSX.Element {
  const modelListId = useId();
  const [values, setValues] = useState<AircraftFormValues>(initial);
  // The fields that have been typed in and left; a complaint appears when the
  // typist moves on from a field rather than when they try to save.
  const [touched, setTouched] = useState<Record<string, true>>({});
  const [submitted, setSubmitted] = useState(false);

  const found = validateAircraft(values);
  const visible: Record<string, string> = {};
  for (const [key, message] of Object.entries(found)) {
    if (submitted || touched[key]) visible[key] = message;
  }

  const shown = { ...visible, ...(serverErrors ?? {}) };

  const handleBlur = (key: string) => () => setTouched((left) => ({ ...left, [key]: true }));

  const set = <K extends keyof AircraftFormValues>(key: K, value: AircraftFormValues[K]): void => {
    setValues((current) => ({ ...current, [key]: value }));
  };

  const suggestions = suggestTypes(values.model);

  /**
   * Take what was typed, and fill the make in when it names one known type.
   *
   * Picking "PA-46 Malibu" from the list should not then need "Piper" typed
   * beside it; typing a model nobody has heard of is still allowed, and an
   * already-typed make is never overwritten.
   */
  const handleModel = (typed: string): void => {
    const known = matchType(typed);
    setValues((current) => ({
      ...current,
      model: typed,
      make: known && !current.make.trim() ? known.make : current.make,
    }));
  };

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    setSubmitted(true);
    if (Object.keys(found).length > 0) return;
    onSubmit(aircraftPayload(values));
  };

  return (
    <form onSubmit={handleSubmit} noValidate>
      <fieldset className="aircraft-form__section">
        <legend className="aircraft-form__legend">Aircraft</legend>
        <div className="aircraft-form__grid">
          <Field
            label="N-number"
            required
            error={shown.n_number}
            hint="Digits, then up to two letters"
          >
            {(field) => (
              <MaskedInput
                {...field}
                className="mono"
                placeholder="N172SP"
                mask={maskNNumber}
                value={values.n_number}
                onValueChange={(next) => set('n_number', next)}
                onBlur={handleBlur('n_number')}
              />
            )}
          </Field>
          <Field label="Year" error={shown.year}>
            {(field) => (
              <MaskedInput
                {...field}
                className="mono"
                inputMode="numeric"
                size={6}
                mask={(raw) => maskDigits(raw, 4)}
                value={values.year}
                onValueChange={(next) => set('year', next)}
                onBlur={handleBlur('year')}
              />
            )}
          </Field>
          <Field label="Make" required error={shown.make}>
            {(field) => (
              <input
                {...field}
                value={values.make}
                onChange={(event) => set('make', event.target.value)}
                onBlur={handleBlur('make')}
              />
            )}
          </Field>
          <Field label="Model" required error={shown.model} hint="Start typing: Mal, 172, RV-7">
            {(field) => (
              <>
                <input
                  {...field}
                  list={modelListId}
                  value={values.model}
                  onChange={(event) => handleModel(event.target.value)}
                  onBlur={handleBlur('model')}
                />
                <datalist id={modelListId}>
                  {suggestions.map((type) => (
                    <option key={type.designator + type.model} value={type.model}>
                      {type.make} · {type.designator}
                    </option>
                  ))}
                </datalist>
              </>
            )}
          </Field>
          <Field label="Seats" error={shown.seats}>
            {(field) => (
              <MaskedInput
                {...field}
                className="mono"
                inputMode="numeric"
                size={4}
                mask={(raw) => maskDigits(raw, 2)}
                value={values.seats}
                onValueChange={(next) => set('seats', next)}
                onBlur={handleBlur('seats')}
              />
            )}
          </Field>
        </div>
      </fieldset>

      <fieldset className="aircraft-form__section">
        <legend className="aircraft-form__legend">Owner</legend>
        <div className="aircraft-form__grid">
          <Field label="Owner type">
            {(field) => (
              <select
                {...field}
                value={values.owner_type}
                onChange={(event) =>
                  set('owner_type', event.target.value as AircraftFormValues['owner_type'])
                }
              >
                {OWNER_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {OWNER_TYPE_LABELS[type]}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Owner name" error={shown.owner_name}>
            {(field) => (
              <input
                {...field}
                value={values.owner_name}
                onChange={(event) => set('owner_name', event.target.value)}
              />
            )}
          </Field>
          <Field label="Owner contact" hint="Email or phone." error={shown.owner_contact}>
            {(field) => (
              <input
                {...field}
                value={values.owner_contact}
                onChange={(event) => set('owner_contact', event.target.value)}
              />
            )}
          </Field>
        </div>
      </fieldset>

      <fieldset className="aircraft-form__section">
        <legend className="aircraft-form__legend">Insurance</legend>
        <div className="aircraft-form__grid">
          <Field label="Carrier" error={shown.insurance_carrier}>
            {(field) => (
              <input
                {...field}
                value={values.insurance_carrier}
                onChange={(event) => set('insurance_carrier', event.target.value)}
              />
            )}
          </Field>
          <Field label="Policy number" error={shown.insurance_policy_number}>
            {(field) => (
              <input
                {...field}
                className="mono"
                value={values.insurance_policy_number}
                onChange={(event) => set('insurance_policy_number', event.target.value)}
              />
            )}
          </Field>
          <Field
            label="Liability per occurrence"
            hint="US dollars; commas write themselves."
            error={shown.liability_per_occurrence ?? shown.insurance_liability_per_occurrence_cents}
          >
            {(field) => (
              <MaskedInput
                {...field}
                className="mono"
                inputMode="decimal"
                mask={maskDollars}
                value={values.liability_per_occurrence}
                onValueChange={(next) => set('liability_per_occurrence', next)}
                onBlur={handleBlur('liability_per_occurrence')}
              />
            )}
          </Field>
          <Field
            label="Liability per person"
            hint="US dollars; commas write themselves."
            error={shown.liability_per_person ?? shown.insurance_liability_per_person_cents}
          >
            {(field) => (
              <MaskedInput
                {...field}
                className="mono"
                inputMode="decimal"
                mask={maskDollars}
                value={values.liability_per_person}
                onValueChange={(next) => set('liability_per_person', next)}
                onBlur={handleBlur('liability_per_person')}
              />
            )}
          </Field>
          <Field
            label="Hull"
            hint="US dollars; commas write themselves."
            error={shown.hull ?? shown.insurance_hull_cents}
          >
            {(field) => (
              <MaskedInput
                {...field}
                className="mono"
                inputMode="decimal"
                mask={maskDollars}
                value={values.hull}
                onValueChange={(next) => set('hull', next)}
                onBlur={handleBlur('hull')}
              />
            )}
          </Field>
          <Field label="Insurance expires" error={shown.insurance_expiration}>
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
      </fieldset>

      {withAdminFields ? (
        <fieldset className="aircraft-form__section">
          <legend className="aircraft-form__legend">Administration</legend>
          <Field label="Notes" error={shown.notes}>
            {(field) => (
              <textarea
                {...field}
                rows={3}
                value={values.notes}
                onChange={(event) => set('notes', event.target.value)}
              />
            )}
          </Field>
          <label className="cluster">
            <input
              type="checkbox"
              checked={values.is_active}
              onChange={(event) => set('is_active', event.target.checked)}
            />
            <span>In service</span>
          </label>
        </fieldset>
      ) : null}

      <div className="cluster aircraft-form__section">
        <Button type="submit" disabled={pending}>
          {pending ? 'Saving…' : submitLabel}
        </Button>
        {handleCancel ? (
          <Button variant="quiet" onClick={handleCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </form>
  );
}
