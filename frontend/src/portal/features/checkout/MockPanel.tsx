/**
 * The mock provider's panel: two buttons, no network beyond our own API.
 *
 * It is what e2e runs and anyone without payment keys uses, and the server
 * refuses it entirely unless `PAYMENTS_MOCK_ENABLED` is on.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { Button } from '@/portal/components/Button';
import { checkoutRequest, completeMockPayment, createCheckout, panelErrorMessage } from './api';
import type { ProviderPanelProps } from './types';

/** Succeed / Fail buttons that drive the mock payment provider directly. */
export function MockPanel({
  amountCents: _amountCents,
  onSuccess,
  onRenewalContribution,
  ...fields
}: ProviderPanelProps): JSX.Element {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function pay(outcome: 'succeed' | 'fail') {
    setError(null);
    setBusy(true);
    try {
      const checkout = await createCheckout(checkoutRequest(fields, 'mock'));
      const result = await completeMockPayment(checkout.payment_id, outcome);
      if (result.status === 'succeeded') {
        onSuccess({ paymentId: checkout.payment_id, membership: result.membership });
      } else {
        setError('The test payment was declined. Nothing was charged.');
      }
    } catch (caught) {
      setError(
        panelErrorMessage(
          caught,
          'The test payment could not be completed.',
          onRenewalContribution,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="checkout__panel stack">
      <p className="muted">
        This deployment has no live payment keys, so payments are simulated. Nothing is charged and
        no card details are collected.
      </p>
      {error ? (
        <p className="checkout__error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="cluster">
        <Button onClick={() => void pay('succeed')} disabled={busy}>
          {busy ? 'Working…' : 'Succeed'}
        </Button>
        <Button variant="quiet" onClick={() => void pay('fail')} disabled={busy}>
          Fail
        </Button>
      </div>
    </div>
  );
}
