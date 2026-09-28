/**
 * The N-number box of the aircraft form: a typeahead over the FAA registry.
 *
 * As the N-number is typed, the registrations whose N-number starts with it are
 * listed under the box, each with its aircraft type, year, and registrant.  Picking
 * one writes its N-number into the box and hands the registration to `onFound`,
 * which fills the form; under the box it then says *From the FAA registry as of*
 * the day of the import behind it, until the box is changed again.  What is typed
 * keeps the N-number mask, so the box only ever holds a well-formed registration.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { Registration } from '@/portal/api/types';
import { formatDate } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { Typeahead } from '@/portal/components/Typeahead';
import { maskNNumber } from '@/portal/masks';
import { aircraftTypeName } from './AircraftTypePicker';
import { useRegistrationSearch } from './api';

/** The fewest characters worth asking the registry about: `N` and one digit. */
const REGISTRATION_SEARCH_MIN_LENGTH = 2;

export interface NNumberFieldProps {
  value: string;
  onValueChange: (next: string) => void;
  /** Called with the registration picked from the list. */
  onFound: (registration: Registration) => void;
  onBlur?: () => void;
  error?: string;
  hint?: string;
}

/** A registration's type, year, and registrant, for the muted end of its line in the list. */
export function registrationMeta(registration: Registration): string {
  const { type, year, registrant_name: registrant } = registration;
  const parts = [aircraftTypeName(type), year === null ? '' : String(year), registrant.trim()];
  return parts.filter((part) => part !== '').join('  ');
}

/** The line under the box for the registration picked, or null before a pick. */
export function registryNote(picked: Registration | null): string | null {
  if (picked === null) return null;
  return `From the FAA registry as of ${formatDate(picked.imported_at)}`;
}

/** The N-number box, the registrations it offers, and the line naming the registry's date. */
export function NNumberField({
  value,
  onValueChange,
  onFound,
  onBlur: handleBlur,
  error,
  hint,
}: NNumberFieldProps): JSX.Element {
  const [picked, setPicked] = useState<Registration | null>(null);

  const handleValueChange = (next: string): void => {
    setPicked(null);
    onValueChange(maskNNumber(next));
  };

  const handlePick = (registration: Registration): void => {
    onValueChange(registration.n_number);
    setPicked(registration);
    onFound(registration);
  };

  return (
    <div className="aircraft-nnumber">
      <Field label="N-number" required error={error} hint={hint}>
        {(field) => (
          <Typeahead
            {...field}
            listLabel="FAA registrations"
            className="mono"
            placeholder="N172SP"
            autoComplete="off"
            value={value}
            onValueChange={handleValueChange}
            onPick={handlePick}
            onBlur={handleBlur}
            useSuggestions={useRegistrationSearch}
            itemKey={(registration) => registration.n_number}
            itemLabel={(registration) => registration.n_number}
            itemMeta={registrationMeta}
            minLength={REGISTRATION_SEARCH_MIN_LENGTH}
          />
        )}
      </Field>
      <p className="aircraft-nnumber__note muted" role="status">
        {registryNote(picked)}
      </p>
    </div>
  );
}
