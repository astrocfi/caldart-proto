/**
 * Change the contribution renewed alongside the dues.
 *
 * The dues themselves are not settable: every charge takes the plan's price on
 * the day, which is what the card above the form says.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { RenewalMandate } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Field } from '@/portal/components/Field';
import { MaskedInput } from '@/portal/components/MaskedInput';
import { useToast } from '@/portal/components/Toast';
import { usePaymentsConfig } from '@/portal/features/checkout/api';
import { dollarsToCents, maskContribution } from '@/portal/features/checkout/ContributionChooser';
import { maskWholeDollars } from '@/portal/masks';
import { useUpdateRenewal } from './api';

export interface ContributionFormProps {
  mandate: RenewalMandate;
  /** Called once the change is saved, or abandoned. */
  onDone: () => void;
}

/** A dollars box over the mandate's contribution, saved with `PATCH /me/renewal`. */
export function ContributionForm({
  mandate,
  onDone: handleDone,
}: ContributionFormProps): JSX.Element {
  const initial =
    mandate.contribution_cents === 0
      ? ''
      : maskWholeDollars(String(Math.floor(mandate.contribution_cents / 100)));
  const [typed, setTyped] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const { data: config } = usePaymentsConfig();
  const update = useUpdateRenewal();
  const toast = useToast();

  async function save(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);
    try {
      // The box holds whole dollars, so a contribution that is not a whole
      // number of them goes back untouched unless the member changes it.
      await update.mutateAsync(
        typed === initial ? mandate.contribution_cents : dollarsToCents(typed),
      );
      toast.show('Contribution saved.', 'success');
      handleDone();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? (caught.fieldErrors.contribution_cents ?? caught.message)
          : 'That contribution could not be saved.',
      );
    }
  }

  return (
    <form className="renewal__contribution stack" onSubmit={(event) => void save(event)}>
      <Field
        label="Contribution renewed each year"
        error={error}
        hint="Whole dollars, on top of the dues. Zero renews the dues alone."
      >
        {(props) => (
          <div className="checkout__other-input">
            <span aria-hidden="true" className="mono">
              $
            </span>
            <MaskedInput
              {...props}
              className="mono"
              inputMode="numeric"
              mask={(raw) => maskContribution(raw, config?.max_contribution_cents ?? null)}
              value={typed}
              onValueChange={(next) => setTyped(next)}
            />
          </div>
        )}
      </Field>
      <div className="cluster">
        <Button type="submit" disabled={update.isPending}>
          {update.isPending ? 'Saving…' : 'Save contribution'}
        </Button>
        <Button variant="quiet" onClick={handleDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
