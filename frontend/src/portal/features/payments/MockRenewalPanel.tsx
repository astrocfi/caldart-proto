/**
 * The mock provider's setup panel: one button, no browser SDK.
 *
 * It is what the end-to-end specs drive and what a deployment without payment
 * keys offers, and the server refuses it unless `PAYMENTS_MOCK_ENABLED` is on.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { Button } from '@/portal/components/Button';
import { panelErrorMessage } from '@/portal/features/checkout/api';
import { renewalSetupRequest, useConfirmRenewal, useStartRenewalSetup } from './api';
import type { RenewalPanelProps } from './types';

/** Saves the mock provider's test card as the method CalDART charges from. */
export function MockRenewalPanel({
  scope,
  onDone: handleDone,
  onRenewalContribution,
  ...fields
}: RenewalPanelProps): JSX.Element {
  const [error, setError] = useState<string | null>(null);
  const start = useStartRenewalSetup(scope);
  const confirm = useConfirmRenewal(scope);
  const isBusy = start.isPending || confirm.isPending;

  async function save(): Promise<void> {
    setError(null);
    try {
      await start.mutateAsync(renewalSetupRequest({ ...fields, provider: 'mock' }));
      await confirm.mutateAsync({ setup_intent_id: '', setup_token: '' });
      handleDone();
    } catch (caught) {
      setError(
        panelErrorMessage(
          caught,
          'That payment method could not be saved. Please try again.',
          onRenewalContribution,
        ),
      );
    }
  }

  return (
    <div className="checkout__panel stack">
      <p className="muted">
        This deployment has no live payment keys, so a test card stands in. Nothing is charged and
        no card details are collected.
      </p>
      {error ? (
        <p className="checkout__error" role="alert">
          {error}
        </p>
      ) : null}
      <Button onClick={() => void save()} disabled={isBusy}>
        {isBusy ? 'Saving…' : 'Save this test card'}
      </Button>
    </div>
  );
}
