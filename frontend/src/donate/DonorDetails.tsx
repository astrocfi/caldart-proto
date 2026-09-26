/**
 * The donation form's **Tell us more (optional)** section, collapsed until opened.
 *
 * Every field here is one of the profile's own, labeled as the portal's profile form
 * labels it, so a donor who later joins finds the same words on their profile.
 * Nothing here is required.
 */
import type { JSX } from 'react';

import type { DonationsConfig } from '@/portal/api/types';
import { CERTIFICATE_TYPES, IFR_OPTIONS } from '@/portal/choices';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { VOLUNTEER_INTERESTS } from '@/portal/features/profile/constants';
import { maskAirportIdentifier, maskPostalCode } from '@/portal/masks';
import type { DonationFormValues } from './form';
import '@/portal/features/profile/profile.css';

/** The optional fields a plain text box edits. */
type TextKey =
  'address_line1' | 'address_line2' | 'city' | 'home_airport_city' | 'air_care_alliance_number';

export interface DonorDetailsProps {
  value: DonationFormValues;
  onChange: (next: DonationFormValues) => void;
  config: Pick<DonationsConfig, 'counties' | 'darts' | 'states'>;
}

/** The optional address, aviation, and volunteer fields, in a closed `<details>`. */
export function DonorDetails({ value, onChange, config }: DonorDetailsProps): JSX.Element {
  const set = <Key extends keyof DonationFormValues>(key: Key, next: DonationFormValues[Key]) =>
    onChange({ ...value, [key]: next });

  const text = (key: TextKey, label: string, autoComplete?: string) => (
    <Field label={label}>
      {(props) => (
        <input
          {...props}
          type="text"
          name={key}
          autoComplete={autoComplete}
          value={value[key]}
          onChange={(event) => set(key, event.target.value)}
        />
      )}
    </Field>
  );

  return (
    <details className="donate__more">
      <summary>Tell us more (optional)</summary>
      <div className="form-grid">
        {text('address_line1', 'Address', 'address-line1')}
        {text('address_line2', 'Address line 2', 'address-line2')}
        {text('city', 'City', 'address-level2')}
        <Field label="State">
          {(props) => (
            <select
              {...props}
              name="state"
              autoComplete="address-level1"
              value={value.state}
              onChange={(event) => set('state', event.target.value)}
            >
              <option value="">—</option>
              {config.states.map((state) => (
                <option key={state.value} value={state.value}>
                  {state.value} — {state.label}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="ZIP code">
          {(props) => (
            <MaskedInput
              {...props}
              name="postal_code"
              inputMode="numeric"
              autoComplete="postal-code"
              size={5}
              placeholder="95035"
              mask={maskPostalCode}
              value={value.postal_code}
              onValueChange={(next) => set('postal_code', next)}
            />
          )}
        </Field>
        <Field label="California county">
          {(props) => (
            <select
              {...props}
              name="county"
              value={value.county}
              onChange={(event) => set('county', event.target.value)}
            >
              <option value="">Not in California</option>
              {config.counties.map((county) => (
                <option key={county} value={county}>
                  {county}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Home airport" hint="Three characters, omit the leading K">
          {(props) => (
            <MaskedInput
              {...props}
              name="home_airport_identifier"
              size={4}
              placeholder="PAO"
              mask={maskAirportIdentifier}
              value={value.home_airport_identifier}
              onValueChange={(next) => set('home_airport_identifier', next)}
            />
          )}
        </Field>
        {text('home_airport_city', 'Home airport city')}
        <Field label="DART">
          {(props) => (
            <select
              {...props}
              name="dart_id"
              value={value.dart_id}
              onChange={(event) => set('dart_id', event.target.value)}
            >
              <option value="">None</option>
              {config.darts.map((dart) => (
                <option key={dart.id} value={String(dart.id)}>
                  {dart.name}
                </option>
              ))}
            </select>
          )}
        </Field>
        {text('air_care_alliance_number', 'Air Care Alliance number')}
        <Field label="Pilot certificate">
          {(props) => (
            <select
              {...props}
              name="pilot_certificate_type"
              value={value.pilot_certificate_type}
              onChange={(event) =>
                set(
                  'pilot_certificate_type',
                  event.target.value as DonationFormValues['pilot_certificate_type'],
                )
              }
            >
              {CERTIFICATE_TYPES.map((choice) => (
                <option key={choice.value} value={choice.value}>
                  {choice.label}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="IFR rated">
          {(props) => (
            <select
              {...props}
              name="ifr_rated"
              value={value.ifr_rated}
              onChange={(event) =>
                set('ifr_rated', event.target.value as DonationFormValues['ifr_rated'])
              }
            >
              {IFR_OPTIONS.map((choice) => (
                <option key={choice.value} value={choice.value}>
                  {choice.label}
                </option>
              ))}
            </select>
          )}
        </Field>
      </div>
      <fieldset>
        <legend>Volunteer interests</legend>
        <div className="checkbox-grid">
          {VOLUNTEER_INTERESTS.map(({ field, label }) => (
            <label key={field} className="checkbox">
              <input
                type="checkbox"
                name={field}
                checked={value.volunteer[field]}
                onChange={(event) =>
                  set('volunteer', { ...value.volunteer, [field]: event.target.checked })
                }
              />
              <span>{label}</span>
            </label>
          ))}
        </div>
      </fieldset>
    </details>
  );
}
