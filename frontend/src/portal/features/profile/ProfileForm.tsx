/**
 * The member profile form (PLAN §4.2, §6.3).
 *
 * One component serves both `/profile` and step 2 of the join wizard, so the
 * two can never drift.  Three fieldsets — Contact, Aviation, Volunteer
 * interests — each a hairline-ruled section, one column on a phone and two on
 * anything wider.
 */
import { useEffect, useId, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';

import type { ProfilePatch, Rating } from '../../api/types';
import { Button } from '../../components/Button';
import { Field } from '../../components/Field';
import { useDarts } from './api';
import {
  CA_COUNTIES,
  CERTIFICATE_TYPES,
  IFR_OPTIONS,
  MEDICAL_TYPES,
  RATINGS,
  VOLUNTEER_INTERESTS,
} from './constants';
import { formToPatch, validateProfileForm } from './form';
import type { ProfileFormErrors, ProfileFormValues } from './form';
import './profile.css';

export interface ProfileFormProps {
  initialValues: ProfileFormValues;
  onSubmit: (patch: ProfilePatch, values: ProfileFormValues) => void;
  submitting?: boolean;
  submitLabel?: string;
  /** Field-keyed messages from a rejected save, merged with the inline ones. */
  serverErrors?: Record<string, string>;
  /** Rendered beside the submit button — a "Back" link in the wizard. */
  secondaryAction?: ReactNode;
}

export function ProfileForm({
  initialValues,
  onSubmit,
  submitting = false,
  submitLabel = 'Save profile',
  serverErrors,
  secondaryAction,
}: ProfileFormProps) {
  const [values, setValues] = useState<ProfileFormValues>(initialValues);
  const [errors, setErrors] = useState<ProfileFormErrors>({});
  const [submitted, setSubmitted] = useState(false);
  const countyListId = useId();
  const darts = useDarts();

  // Re-check as the member types, but only once they have tried to submit —
  // nobody wants to be told a field is empty before they reach it.
  useEffect(() => {
    if (submitted) setErrors(validateProfileForm(values));
  }, [submitted, values]);

  function set<K extends keyof ProfileFormValues>(key: K, value: ProfileFormValues[K]) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  function toggleRating(rating: Rating, on: boolean) {
    setValues((current) => ({
      ...current,
      ratings: on
        ? [...current.ratings, rating]
        : current.ratings.filter((value) => value !== rating),
    }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    const found = validateProfileForm(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    onSubmit(formToPatch(values), values);
  }

  /** Inline rules win; a server message fills in anything they missed. */
  const errorFor = (key: keyof ProfileFormValues): string | null =>
    errors[key] ?? serverErrors?.[key] ?? null;

  const hasErrors = Object.keys(errors).length > 0;

  return (
    <form onSubmit={handleSubmit} noValidate className="profile-form">
      <fieldset>
        <legend>Contact</legend>
        <div className="form-grid">
          <Field label="Phone" required error={errorFor('phone')}>
            {(props) => (
              <input
                {...props}
                type="tel"
                name="phone"
                autoComplete="tel"
                value={values.phone}
                onChange={(event) => set('phone', event.target.value)}
              />
            )}
          </Field>
          <Field label="Alternate phone" error={errorFor('phone_alt')}>
            {(props) => (
              <input
                {...props}
                type="tel"
                name="phone_alt"
                value={values.phone_alt}
                onChange={(event) => set('phone_alt', event.target.value)}
              />
            )}
          </Field>
          <Field label="Address" required error={errorFor('address_line1')}>
            {(props) => (
              <input
                {...props}
                type="text"
                name="address_line1"
                autoComplete="address-line1"
                value={values.address_line1}
                onChange={(event) => set('address_line1', event.target.value)}
              />
            )}
          </Field>
          <Field label="Address line 2" error={errorFor('address_line2')}>
            {(props) => (
              <input
                {...props}
                type="text"
                name="address_line2"
                autoComplete="address-line2"
                value={values.address_line2}
                onChange={(event) => set('address_line2', event.target.value)}
              />
            )}
          </Field>
          <Field label="City" required error={errorFor('city')}>
            {(props) => (
              <input
                {...props}
                type="text"
                name="city"
                autoComplete="address-level2"
                value={values.city}
                onChange={(event) => set('city', event.target.value)}
              />
            )}
          </Field>
          <Field label="State" error={errorFor('state')} hint="Two letters, e.g. CA">
            {(props) => (
              <input
                {...props}
                type="text"
                name="state"
                autoComplete="address-level1"
                maxLength={2}
                size={2}
                value={values.state}
                onChange={(event) => set('state', event.target.value.toUpperCase())}
              />
            )}
          </Field>
          <Field label="ZIP code" required error={errorFor('postal_code')}>
            {(props) => (
              <input
                {...props}
                type="text"
                name="postal_code"
                inputMode="numeric"
                autoComplete="postal-code"
                value={values.postal_code}
                onChange={(event) => set('postal_code', event.target.value)}
              />
            )}
          </Field>
          <Field label="County" error={errorFor('county')} hint="California counties are suggested">
            {(props) => (
              <>
                <input
                  {...props}
                  type="text"
                  name="county"
                  list={countyListId}
                  value={values.county}
                  onChange={(event) => set('county', event.target.value)}
                />
                <datalist id={countyListId}>
                  {CA_COUNTIES.map((county) => (
                    <option key={county} value={county} />
                  ))}
                </datalist>
              </>
            )}
          </Field>
          <Field label="Emergency contact" error={errorFor('emergency_contact_name')}>
            {(props) => (
              <input
                {...props}
                type="text"
                name="emergency_contact_name"
                value={values.emergency_contact_name}
                onChange={(event) => set('emergency_contact_name', event.target.value)}
              />
            )}
          </Field>
          <Field label="Emergency contact phone" error={errorFor('emergency_contact_phone')}>
            {(props) => (
              <input
                {...props}
                type="tel"
                name="emergency_contact_phone"
                value={values.emergency_contact_phone}
                onChange={(event) => set('emergency_contact_phone', event.target.value)}
              />
            )}
          </Field>
        </div>
      </fieldset>

      <fieldset>
        <legend>Aviation</legend>
        <div className="form-grid">
          <Field label="Home airport" error={errorFor('home_airport_identifier')} hint="e.g. PAO">
            {(props) => (
              <input
                {...props}
                type="text"
                name="home_airport_identifier"
                maxLength={8}
                value={values.home_airport_identifier}
                onChange={(event) =>
                  set('home_airport_identifier', event.target.value.toUpperCase())
                }
              />
            )}
          </Field>
          <Field label="Home airport city" error={errorFor('home_airport_city')}>
            {(props) => (
              <input
                {...props}
                type="text"
                name="home_airport_city"
                value={values.home_airport_city}
                onChange={(event) => set('home_airport_city', event.target.value)}
              />
            )}
          </Field>
          <Field label="DART" error={errorFor('dart_id')} hint="The team you fly with">
            {(props) => (
              <select
                {...props}
                name="dart_id"
                value={values.dart_id}
                onChange={(event) => set('dart_id', event.target.value)}
              >
                <option value="">{darts.isPending ? 'Loading DARTs…' : 'Not decided yet'}</option>
                {(darts.data ?? []).map((dart) => (
                  <option key={dart.id} value={String(dart.id)}>
                    {dart.airport_identifier
                      ? `${dart.name} (${dart.airport_identifier})`
                      : dart.name}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Air Care Alliance number" error={errorFor('air_care_alliance_number')}>
            {(props) => (
              <input
                {...props}
                type="text"
                name="air_care_alliance_number"
                value={values.air_care_alliance_number}
                onChange={(event) => set('air_care_alliance_number', event.target.value)}
              />
            )}
          </Field>
          <Field label="Pilot certificate" error={errorFor('pilot_certificate_type')}>
            {(props) => (
              <select
                {...props}
                name="pilot_certificate_type"
                value={values.pilot_certificate_type}
                onChange={(event) =>
                  set(
                    'pilot_certificate_type',
                    event.target.value as ProfileFormValues['pilot_certificate_type'],
                  )
                }
              >
                {CERTIFICATE_TYPES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field
            label="Certificate number"
            error={errorFor('certificate_number')}
            required={values.pilot_certificate_type !== 'none'}
          >
            {(props) => (
              <input
                {...props}
                type="text"
                name="certificate_number"
                className="mono"
                value={values.certificate_number}
                onChange={(event) => set('certificate_number', event.target.value)}
              />
            )}
          </Field>
          <Field label="Instrument current" error={errorFor('ifr_rated')}>
            {(props) => (
              <select
                {...props}
                name="ifr_rated"
                value={values.ifr_rated}
                onChange={(event) =>
                  set('ifr_rated', event.target.value as ProfileFormValues['ifr_rated'])
                }
              >
                {IFR_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Medical" error={errorFor('medical_type')}>
            {(props) => (
              <select
                {...props}
                name="medical_type"
                value={values.medical_type}
                onChange={(event) =>
                  set('medical_type', event.target.value as ProfileFormValues['medical_type'])
                }
              >
                {MEDICAL_TYPES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field
            label="Medical expires"
            error={errorFor('medical_expiration')}
            required={values.medical_type !== 'none'}
          >
            {(props) => (
              <input
                {...props}
                type="date"
                name="medical_expiration"
                value={values.medical_expiration}
                onChange={(event) => set('medical_expiration', event.target.value)}
              />
            )}
          </Field>
          <Field label="Last flight review" error={errorFor('flight_review_date')}>
            {(props) => (
              <input
                {...props}
                type="date"
                name="flight_review_date"
                value={values.flight_review_date}
                onChange={(event) => set('flight_review_date', event.target.value)}
              />
            )}
          </Field>
          <Field label="Total hours" error={errorFor('total_hours')}>
            {(props) => (
              <input
                {...props}
                type="text"
                name="total_hours"
                inputMode="numeric"
                value={values.total_hours}
                onChange={(event) => set('total_hours', event.target.value)}
              />
            )}
          </Field>
        </div>

        <fieldset className="checkbox-set">
          <legend>Ratings</legend>
          <div className="checkbox-grid">
            {RATINGS.map((rating) => (
              <label key={rating.value} className="checkbox">
                <input
                  type="checkbox"
                  name="ratings"
                  value={rating.value}
                  checked={values.ratings.includes(rating.value)}
                  onChange={(event) => toggleRating(rating.value, event.target.checked)}
                />
                <span>{rating.label}</span>
              </label>
            ))}
          </div>
        </fieldset>
      </fieldset>

      <fieldset>
        <legend>Volunteer interests</legend>
        <p className="muted profile-form__note">
          CalDART runs on volunteers. Tick anything you would be willing to help with.
        </p>
        <div className="checkbox-grid">
          {VOLUNTEER_INTERESTS.map((interest) => (
            <label key={interest.field} className="checkbox">
              <input
                type="checkbox"
                name={interest.field}
                checked={values[interest.field]}
                onChange={(event) => set(interest.field, event.target.checked)}
              />
              <span>{interest.label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {submitted && hasErrors ? (
        <p className="field__error" role="alert">
          Check the highlighted fields and try again.
        </p>
      ) : null}

      <div className="cluster profile-form__actions">
        <Button type="submit" disabled={submitting}>
          {submitting ? 'Saving…' : submitLabel}
        </Button>
        {secondaryAction}
      </div>
    </form>
  );
}
