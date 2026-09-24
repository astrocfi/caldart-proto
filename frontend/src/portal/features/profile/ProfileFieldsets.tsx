/**
 * The three profile fieldsets — Contact, Aviation (with Ratings) and Volunteer
 * interests — as one controlled component.
 *
 * `/profile`, join step 2, "New member" and the Profile tab of a member record
 * all edit the same `ProfileFormValues`, so they all render this: one set of
 * labels, hints, input types and constraints, whoever is typing.  The only
 * difference between a member's screen and an administrator's is
 * `markRequired`, which stars the fields that make a profile complete.  The
 * administrator's screens leave it off, because a half-known record is a
 * normal thing for them to save.
 *
 * Validation, submission, and the administrator-only fields belong to the
 * caller.
 */
import { useId } from 'react';
import type { JSX } from 'react';

import type { CaliforniaCounty, Dart, Rating, UsState } from '@/portal/api/types';
import { CATEGORY_RATINGS, INSTRUCTOR_RATINGS, US_STATES } from '@/portal/choices';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import {
  maskAirportIdentifier,
  maskDigits,
  maskExtension,
  maskPhone,
  maskPostalCode,
} from '@/portal/masks';
import {
  CA_COUNTIES,
  CERTIFICATE_TYPES,
  IFR_OPTIONS,
  MEDICAL_TYPES,
  VOLUNTEER_INTERESTS,
} from './constants';
import type { Choice } from './constants';
import type { ProfileFormErrors, ProfileFormValues } from './form';
import './profile.css';

/** The form keys holding free text, which is every key a plain input can edit. */
type TextKey = {
  [Key in keyof ProfileFormValues]: string extends ProfileFormValues[Key] ? Key : never;
}[keyof ProfileFormValues];

/** The form keys holding a coded value, which a `<select>` picks from a list. */
type CodedKey = 'pilot_certificate_type' | 'ifr_rated' | 'medical_type';

/** The two rows of ratings, as the form lays them out. */
const RATING_ROWS: readonly (readonly Choice<Rating>[])[] = [CATEGORY_RATINGS, INSTRUCTOR_RATINGS];

interface TextFieldOptions {
  label: string;
  type?: 'text' | 'tel' | 'date';
  autoComplete?: string;
  inputMode?: 'numeric' | 'tel';
  placeholder?: string;
  maxLength?: number;
  size?: number;
  className?: string;
  hint?: string;
  /** Starred, and only when the caller asked for markers. */
  required?: boolean;
  /**
   * Applied to every keystroke, so a character that cannot belong in the field
   * is never typed into it and the format's punctuation is written for the
   * member.  See `@/portal/masks`.
   */
  mask?: (raw: string) => string;
}

export interface ProfileFieldsetsProps {
  value: ProfileFormValues;
  onChange: (next: ProfileFormValues) => void;
  /** Field-keyed messages, each rendered beside the input it belongs to. */
  errors?: ProfileFormErrors;
  darts: Dart[];
  /** Say so in the empty DART option while the list is still on its way. */
  dartsLoading?: boolean;
  /** Star the fields a member has to fill in before a profile counts as complete. */
  markRequired?: boolean;
}

/**
 * Render the profile fieldsets for whoever is editing the record.
 *
 * @param value - the profile being edited; the component holds no state of its own.
 * @param onChange - called with the whole next value on every edit.
 */
export function ProfileFieldsets({
  value,
  onChange,
  errors = {},
  darts,
  dartsLoading = false,
  markRequired = false,
}: ProfileFieldsetsProps): JSX.Element {
  const extensionIds = useId();

  const set = <Key extends keyof ProfileFormValues>(key: Key, next: ProfileFormValues[Key]) =>
    onChange({ ...value, [key]: next });

  const toggleRating = (rating: Rating, checked: boolean) =>
    set(
      'ratings',
      checked ? [...value.ratings, rating] : value.ratings.filter((item) => item !== rating),
    );

  const text = (key: TextKey, options: TextFieldOptions) => {
    const { label, hint, required = false, mask, ...input } = options;
    return (
      <Field label={label} hint={hint} error={errors[key]} required={markRequired && required}>
        {(props) =>
          mask ? (
            <MaskedInput
              {...props}
              type="text"
              {...input}
              name={key}
              mask={mask}
              value={value[key]}
              onValueChange={(next) => set(key, next)}
            />
          ) : (
            <input
              {...props}
              type="text"
              {...input}
              name={key}
              value={value[key]}
              onChange={(event) => set(key, event.target.value)}
            />
          )
        }
      </Field>
    );
  };

  /**
   * A number and its extension as one field, on one line.
   *
   * Both are fixed-width now that the format is fixed, so the pair fits the
   * column a single phone box used to fill.
   */
  const phone = (
    key: TextKey,
    extensionKey: TextKey,
    label: string,
    options: { required?: boolean; autoComplete?: string; hint?: string } = {},
  ) => (
    <Field
      label={label}
      hint={options.hint}
      error={errors[key] ?? errors[extensionKey]}
      required={markRequired && (options.required ?? false)}
    >
      {(props) => (
        <span className="field-pair">
          <MaskedInput
            {...props}
            type="tel"
            inputMode="tel"
            className="field-pair__main"
            autoComplete={options.autoComplete}
            name={key}
            placeholder="415-555-0100"
            mask={maskPhone}
            value={value[key]}
            onValueChange={(next) => set(key, next)}
          />
          <label className="field-pair__extension" htmlFor={`${extensionIds}-${extensionKey}`}>
            <span>ext.</span>
            <MaskedInput
              id={`${extensionIds}-${extensionKey}`}
              inputMode="numeric"
              name={extensionKey}
              mask={maskExtension}
              value={value[extensionKey]}
              onValueChange={(next) => set(extensionKey, next)}
            />
          </label>
        </span>
      )}
    </Field>
  );

  const coded = <Key extends CodedKey>(
    key: Key,
    label: string,
    choices: readonly Choice<ProfileFormValues[Key]>[],
  ) => (
    <Field label={label} error={errors[key]}>
      {(props) => (
        <select
          {...props}
          name={key}
          value={value[key]}
          onChange={(event) => set(key, event.target.value as ProfileFormValues[Key])}
        >
          {choices.map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  );

  return (
    <>
      <fieldset>
        <legend>Contact</legend>
        <div className="form-grid">
          {phone('phone', 'phone_extension', 'Phone', {
            required: true,
            autoComplete: 'tel',
            hint: 'Ten digits; the dashes write themselves',
          })}
          {phone('phone_alt', 'phone_alt_extension', 'Alternate phone')}
          {text('address_line1', {
            label: 'Address',
            autoComplete: 'address-line1',
            required: true,
          })}
          {text('address_line2', { label: 'Address line 2', autoComplete: 'address-line2' })}
          {text('city', { label: 'City', autoComplete: 'address-level2', required: true })}
          <Field label="State" error={errors.state} required={markRequired}>
            {(props) => (
              <select
                {...props}
                name="state"
                autoComplete="address-level1"
                value={value.state}
                onChange={(event) => set('state', event.target.value as UsState)}
              >
                {US_STATES.map((state) => (
                  <option key={state.value} value={state.value}>
                    {state.value} — {state.label}
                  </option>
                ))}
              </select>
            )}
          </Field>
          {text('postal_code', {
            label: 'ZIP code',
            inputMode: 'numeric',
            autoComplete: 'postal-code',
            size: 5,
            placeholder: '95035',
            required: true,
            mask: maskPostalCode,
          })}
          <Field label="California county" error={errors.county}>
            {(props) => (
              <select
                {...props}
                name="county"
                value={value.county}
                onChange={(event) => set('county', event.target.value as CaliforniaCounty | '')}
              >
                <option value="">Not in California</option>
                {CA_COUNTIES.map((county) => (
                  <option key={county} value={county}>
                    {county}
                  </option>
                ))}
              </select>
            )}
          </Field>
          {text('emergency_contact_name', { label: 'Emergency contact' })}
          {phone(
            'emergency_contact_phone',
            'emergency_contact_phone_extension',
            'Emergency contact phone',
          )}
        </div>
      </fieldset>

      <fieldset>
        <legend>Aviation</legend>
        <div className="form-grid">
          {text('home_airport_identifier', {
            label: 'Home airport',
            size: 4,
            placeholder: 'PAO',
            hint: 'Three characters, no leading K',
            mask: maskAirportIdentifier,
          })}
          {text('home_airport_city', { label: 'Home airport city' })}
          <Field label="DART" error={errors.dart_id} hint="The team you fly with">
            {(props) => (
              <select
                {...props}
                name="dart_id"
                value={value.dart_id}
                onChange={(event) => set('dart_id', event.target.value)}
              >
                <option value="">{dartsLoading ? 'Loading DARTs…' : 'Not decided yet'}</option>
                {darts.map((dart) => (
                  <option key={dart.id} value={String(dart.id)}>
                    {dart.airport_identifier
                      ? `${dart.name} (${dart.airport_identifier})`
                      : dart.name}
                  </option>
                ))}
              </select>
            )}
          </Field>
          {text('air_care_alliance_number', { label: 'Air Care Alliance number' })}
          {coded('pilot_certificate_type', 'Pilot certificate', CERTIFICATE_TYPES)}
          {text('certificate_number', {
            label: 'Certificate number',
            className: 'mono',
            required: value.pilot_certificate_type !== 'none',
          })}
          {coded('ifr_rated', 'IFR rated', IFR_OPTIONS)}
          {coded('medical_type', 'Medical', MEDICAL_TYPES)}
          {text('medical_expiration', {
            label: 'Medical expires',
            type: 'date',
            required: value.medical_type !== 'none',
          })}
          {text('flight_review_date', { label: 'Last flight review', type: 'date' })}
          {text('total_hours', {
            label: 'Total hours',
            inputMode: 'numeric',
            size: 6,
            mask: (raw) => maskDigits(raw, 5),
          })}
          <Field label="Aircraft" error={errors.flies_rented_aircraft}>
            {() => (
              <label className="checkbox">
                <input
                  type="checkbox"
                  name="flies_rented_aircraft"
                  checked={value.flies_rented_aircraft}
                  onChange={(event) => set('flies_rented_aircraft', event.target.checked)}
                />
                <span>I fly rented or borrowed aircraft</span>
              </label>
            )}
          </Field>
        </div>

        <fieldset className="checkbox-set">
          <legend>Ratings</legend>
          {RATING_ROWS.map((row) => (
            <div className="checkbox-row" key={row[0]?.value}>
              {row.map((rating) => (
                <label key={rating.value} className="checkbox">
                  <input
                    type="checkbox"
                    name="ratings"
                    value={rating.value}
                    checked={value.ratings.includes(rating.value)}
                    onChange={(event) => toggleRating(rating.value, event.target.checked)}
                  />
                  <span>{rating.label}</span>
                </label>
              ))}
            </div>
          ))}
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
                checked={value[interest.field]}
                onChange={(event) => set(interest.field, event.target.checked)}
              />
              <span>{interest.label}</span>
            </label>
          ))}
        </div>
      </fieldset>
    </>
  );
}
