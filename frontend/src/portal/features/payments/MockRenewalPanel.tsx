/**
 * The mock provider's setup panel: one button, no browser SDK.
 *
 * It is what the end-to-end specs drive and what a deployment without payment
 * keys offers, and the server refuses it unless `PAYMENTS_MOCK_ENABLED` is on.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import { Button } from '@/portal/components/Button';
import { renewalSetupRequest, useConfirmRenewal, useStartRenewalSetup } from './api';
import type { RenewalPanelProps } from './types';

/** Saves the mock provider's test card as the method CalDART renews from. */
export function MockRenewalPanel({
  plan,
  contributionCents,
  onDone: handleDone,
}: RenewalPanelProps): JSX.Element {
  const [error, setError] = useState<string | null>(null);
  const start = useStartRenewalSetup();
  const confirm = useConfirmRenewal();
  const isBusy = start.isPending || confirm.isPending;

  async function save(): Promise<void> {
    setError(null);
    try {
      await start.mutateAsync(renewalSetupRequest(plan, contributionCents, 'mock'));
      await confirm.mutateAsync({ setup_intent_id: '', setup_token: '' });
      handleDone();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'That payment method could not be saved. Please try again.',
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
