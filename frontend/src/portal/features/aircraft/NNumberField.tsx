/**
 * The N-number box of the aircraft forms, with **Look up** beside it.
 *
 * A Look up asks the FAA registry for the registration and hands what it finds
 * to `onFound`, which fills the form; under the box it then says *From the FAA
 * registry as of* the day of the import behind the answer.  A registration the
 * registry does not hold reads *Not in the FAA registry* and leaves the form
 * alone, and a lookup that fails shows nothing.  Leaving the box with a value
 * that could be a US registration looks it up too, once per registration, and
 * never for the registration a saved record already has.
 */
import { useRef, useState } from 'react';
import type { JSX } from 'react';

import type { Registration } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { formatDate } from '@/portal/components/DateText';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { maskNNumber } from '@/portal/masks';
import type { RegistryLookup } from './api';
import { lookupRegistration } from './api';
import { N_NUMBER_RE } from './form';
import { normalizeNNumber } from './insurance';

export interface NNumberFieldProps {
  value: string;
  onValueChange: (next: string) => void;
  /** Called with the registration a Look up found. */
  onFound: (registration: Registration) => void;
  onBlur?: () => void;
  error?: string;
  hint?: string;
  /** The registration the saved record already has, which leaving the box never looks up. */
  savedNNumber?: string;
}

/** The line under the box for what the last Look up learned, or null for nothing. */
export function lookupNote(lookup: RegistryLookup | null): string | null {
  if (lookup === null || lookup.status === 'failed') return null;
  if (lookup.status === 'missing') return 'Not in the FAA registry';
  return `From the FAA registry as of ${formatDate(lookup.registration.imported_at)}`;
}

/** The N-number box, its Look up button, and the line saying what the registry answered. */
export function NNumberField({
  value,
  onValueChange,
  onFound,
  onBlur,
  error,
  hint,
  savedNNumber = '',
}: NNumberFieldProps): JSX.Element {
  const [lookup, setLookup] = useState<RegistryLookup | null>(null);
  // The registration last asked about, starting with the saved record's own, so
  // passing through the box of a saved record asks nothing.
  const lastAsked = useRef(normalizeNNumber(savedNNumber));
  // The registration being asked about right now.  A press of Look up leaves the
  // box first, and that blur has already asked, so the press does not ask twice.
  const pending = useRef<string | null>(null);
  // Only the newest lookup's answer is shown, whatever order the answers arrive in,
  // and none once the box has changed since it was asked.
  const latest = useRef(0);

  const lookUp = async (nNumber: string): Promise<void> => {
    lastAsked.current = nNumber;
    pending.current = nNumber;
    latest.current += 1;
    const ticket = latest.current;
    const answer = await lookupRegistration(nNumber);
    if (ticket !== latest.current) return;
    pending.current = null;
    setLookup(answer);
    if (answer.status === 'found') onFound(answer.registration);
  };

  const handleValueChange = (next: string): void => {
    // An answer still on its way describes the registration the box held before,
    // so it is dropped, and that registration may be asked about again.
    if (pending.current !== null) lastAsked.current = '';
    pending.current = null;
    latest.current += 1;
    setLookup(null);
    onValueChange(next);
  };

  const handleLookUp = (): void => {
    const nNumber = normalizeNNumber(value);
    if (nNumber === '' || nNumber === pending.current) return;
    void lookUp(nNumber);
  };

  const handleBlur = (): void => {
    onBlur?.();
    const nNumber = normalizeNNumber(value);
    if (!N_NUMBER_RE.test(nNumber) || nNumber === lastAsked.current) return;
    void lookUp(nNumber);
  };

  const note = lookupNote(lookup);

  return (
    <div className="aircraft-lookup">
      <Field label="N-number" required error={error} hint={hint}>
        {(field) => (
          <div className="aircraft-lookup__row">
            <MaskedInput
              {...field}
              className="mono"
              placeholder="N172SP"
              mask={maskNNumber}
              value={value}
              onValueChange={handleValueChange}
              onBlur={handleBlur}
            />
            <Button
              variant="secondary"
              small
              onClick={handleLookUp}
              disabled={normalizeNNumber(value) === ''}
            >
              Look up
            </Button>
          </div>
        )}
      </Field>
      <p className="aircraft-lookup__note muted" role="status">
        {note}
      </p>
    </div>
  );
}
