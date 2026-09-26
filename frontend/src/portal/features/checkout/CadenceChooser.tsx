/**
 * How often a recurring donation charges: monthly, quarterly, or yearly.
 *
 * The same three radios sit under the amount at the Donate screen and in the form
 * that changes a donation already set up, so a giver changes their mind in the
 * words they made it up in.
 */
import type { JSX } from 'react';

import type { MandateCadence } from '@/portal/api/types';
import { CADENCE_LABELS, CADENCE_ORDER } from '@/portal/features/payments/labels';

export interface CadenceChooserProps {
  value: MandateCadence;
  onChange: (cadence: MandateCadence) => void;
  disabled?: boolean;
}

/** The three cadence radios, as one fieldset. */
export function CadenceChooser({
  value,
  onChange,
  disabled = false,
}: CadenceChooserProps): JSX.Element {
  return (
    <fieldset className="checkout__cadence">
      <legend>How often</legend>
      <div className="cluster">
        {CADENCE_ORDER.map((cadence) => (
          <label key={cadence} className="checkout__cadence-option">
            <input
              type="radio"
              name="cadence"
              value={cadence}
              checked={cadence === value}
              disabled={disabled}
              onChange={() => onChange(cadence)}
            />
            <span>{CADENCE_LABELS[cadence]}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
