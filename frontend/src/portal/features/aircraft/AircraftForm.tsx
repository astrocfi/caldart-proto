/**
 * The full aircraft record, in four sections: the airframe, its owner, its
 * insurance and the administrator's own notes.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { AircraftPatch } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import './aircraft.css';
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
  const [values, setValues] = useState<AircraftFormValues>(initial);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const shown = { ...errors, ...(serverErrors ?? {}) };

  const set = <K extends keyof AircraftFormValues>(key: K, value: AircraftFormValues[K]): void => {
    setValues((current) => ({ ...current, [key]: value }));
  };

  const handleSubmit = (event: React.FormEvent): void => {
    event.preventDefault();
    const found = validateAircraft(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    onSubmit(aircraftPayload(values));
  };

  return (
    <form onSubmit={handleSubmit} noValidate>
      <fieldset className="aircraft-form__section">
        <legend className="aircraft-form__legend">Aircraft</legend>
        <div className="aircraft-form__grid">
          <Field label="N-number" required error={shown.n_number}>
            {(field) => (
              <input
                {...field}
                className="mono"
                value={values.n_number}
                onChange={(event) => set('n_number', event.target.value)}
              />
            )}
          </Field>
          <Field label="Year" error={shown.year}>
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
          <Field label="Make" required error={shown.make}>
            {(field) => (
              <input
                {...field}
                value={values.make}
                onChange={(event) => set('make', event.target.value)}
              />
            )}
          </Field>
          <Field label="Model" required error={shown.model}>
            {(field) => (
              <input
                {...field}
                value={values.model}
                onChange={(event) => set('model', event.target.value)}
              />
            )}
          </Field>
          <Field label="Seats" error={shown.seats}>
            {(field) => (
              <input
                {...field}
                className="mono"
                inputMode="numeric"
                value={values.seats}
                onChange={(event) => set('seats', event.target.value)}
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
            hint="US dollars."
            error={shown.liability_per_occurrence ?? shown.insurance_liability_per_occurrence_cents}
          >
            {(field) => (
              <input
                {...field}
                className="mono"
                inputMode="decimal"
                value={values.liability_per_occurrence}
                onChange={(event) => set('liability_per_occurrence', event.target.value)}
              />
            )}
          </Field>
          <Field
            label="Liability per person"
            hint="US dollars."
            error={shown.liability_per_person ?? shown.insurance_liability_per_person_cents}
          >
            {(field) => (
              <input
                {...field}
                className="mono"
                inputMode="decimal"
                value={values.liability_per_person}
                onChange={(event) => set('liability_per_person', event.target.value)}
              />
            )}
          </Field>
          <Field label="Hull" hint="US dollars." error={shown.hull ?? shown.insurance_hull_cents}>
            {(field) => (
              <input
                {...field}
                className="mono"
                inputMode="decimal"
                value={values.hull}
                onChange={(event) => set('hull', event.target.value)}
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
