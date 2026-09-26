/**
 * Stripe's Payment Element in setup mode.
 *
 * Nothing is charged here: the element collects a card and confirms a
 * SetupIntent, which is what gives CalDART permission to charge it again when
 * the membership runs out.  `confirmSetup` runs with `redirect: 'if_required'`,
 * so a card that needs no bank confirmation never leaves the page; one that does
 * comes back to `/portal/payments` with the SetupIntent and the authority it was
 * for in the query string, and that authority's card confirms it there.
 */
import { Elements, PaymentElement, useElements, useStripe } from '@stripe/react-stripe-js';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { MandateScope } from '@/portal/api/queries';
import type { RenewalSetupRequest } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { useDebounced } from '@/portal/components/useDebounced';
import { isAbortError, panelErrorMessage } from '@/portal/features/checkout/api';
import {
  AMOUNT_DEBOUNCE_MS,
  appearanceFromTokens,
  stripeFor,
} from '@/portal/features/checkout/StripePanel';
import type { RenewalSetupFields } from './api';
import { renewalSetupRequest, startRenewalSetup, useConfirmRenewal } from './api';
import { SETUP_SCOPE_PARAM } from './setupReturn';
import type { RenewalPanelProps } from './types';

/**
 * Where Stripe sends the browser back for a card that needs a bank confirmation.
 *
 * The Payments screen, told which authority the card was for, so the right card
 * there finishes the setup.
 */
function returnUrl(scope: MandateScope): string {
  const origin = typeof window === 'undefined' ? '' : window.location.origin;
  return `${origin}/portal/payments?${SETUP_SCOPE_PARAM}=${scope}`;
}

/**
 * The setup request for the current selection, once that selection has held still.
 *
 * It travels through `useDebounced` as its own JSON, exactly as the checkout's
 * request does, so a member typing an amount digit by digit asks Stripe for one
 * SetupIntent rather than one per keystroke.  The object handed back keeps its
 * identity for as long as the JSON does, which is what lets the effect depend on
 * it and nothing else.
 */
function useSettledSetup(fields: Omit<RenewalSetupFields, 'provider'>): RenewalSetupRequest {
  const wanted = JSON.stringify(renewalSetupRequest({ ...fields, provider: 'stripe' }));
  const settled = useDebounced(wanted, AMOUNT_DEBOUNCE_MS);
  return useMemo(() => JSON.parse(settled) as RenewalSetupRequest, [settled]);
}

export interface StripeRenewalPanelProps extends RenewalPanelProps {
  publishableKey: string;
}

/** Starts a SetupIntent for the chosen plan, then mounts the Payment Element. */
export function StripeRenewalPanel({
  publishableKey,
  scope,
  onDone: handleDone,
  onRenewalContribution,
  ...fields
}: StripeRenewalPanelProps): JSX.Element {
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const stripePromise = useMemo(() => stripeFor(publishableKey), [publishableKey]);
  const appearance = useMemo(() => appearanceFromTokens(), []);
  const settled = useSettledSetup(fields);

  useEffect(() => {
    const controller = new AbortController();
    setClientSecret(null);
    setError(null);

    startRenewalSetup(scope, settled, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        if (response.provider !== 'stripe' || !response.client.client_secret) {
          setError('Stripe did not return a setup session. Please try again.');
          return;
        }
        setClientSecret(response.client.client_secret);
      })
      .catch((caught: unknown) => {
        if (isAbortError(caught) || controller.signal.aborted) return;
        setError(
          panelErrorMessage(
            caught,
            'Stripe could not start saving that card.',
            onRenewalContribution,
          ),
        );
      });

    // Abandon the request rather than only ignore its answer. A StrictMode
    // remount aborts before `fetch` dispatches, so the member's pending
    // authority is written once, not twice.
    return () => {
      controller.abort();
    };
  }, [scope, settled, onRenewalContribution]);

  if (error) {
    return (
      <div className="checkout__panel">
        <p className="checkout__error" role="alert">
          {error}
        </p>
      </div>
    );
  }

  if (clientSecret === null) {
    return (
      <div className="checkout__panel">
        <p className="muted" role="status">
          Preparing a secure form…
        </p>
      </div>
    );
  }

  return (
    <div className="checkout__panel">
      <Elements key={clientSecret} stripe={stripePromise} options={{ clientSecret, appearance }}>
        <StripeSetupForm scope={scope} onDone={handleDone} />
      </Elements>
    </div>
  );
}

/** The Payment Element plus its submit button, confirming the SetupIntent on submit. */
function StripeSetupForm({
  scope,
  onDone,
}: {
  scope: MandateScope;
  onDone: () => void;
}): JSX.Element {
  const stripe = useStripe();
  const elements = useElements();
  const confirm = useConfirmRenewal(scope);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (!stripe || !elements) return;

    setIsBusy(true);
    setError(null);
    try {
      const confirmation = await stripe.confirmSetup({
        elements,
        confirmParams: { return_url: returnUrl(scope) },
        redirect: 'if_required',
      });
      if (confirmation.error) {
        setError(confirmation.error.message ?? 'That card could not be saved.');
        return;
      }
      await confirm.mutateAsync({
        setup_intent_id: confirmation.setupIntent?.id ?? '',
        setup_token: '',
      });
      onDone();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'That card could not be saved.');
    } finally {
      if (isMounted.current) setIsBusy(false);
    }
  }

  return (
    <form onSubmit={(event) => void submit(event)} className="stack">
      <PaymentElement options={{ layout: 'tabs' }} />
      {error ? (
        <p className="checkout__error" role="alert">
          {error}
        </p>
      ) : null}
      <Button type="submit" disabled={!stripe || isBusy}>
        {isBusy ? 'Saving…' : 'Save this card'}
      </Button>
      <p className="checkout__fineprint muted">
        Card details go straight to Stripe; CalDART never sees them. Nothing is charged today.
      </p>
    </form>
  );
}
