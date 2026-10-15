/**
 * Stripe's Payment Element.
 *
 * Card, Apple Pay, Google Pay and Link all arrive through this one element:
 * the server enabled `automatic_payment_methods`, so Stripe shows whichever
 * the browser and the account support.  Opening the tab creates the
 * PaymentIntent; changing the amount afterwards quietly creates a new one, and so
 * does a decline, since the server cancels a declined intent.
 *
 * `confirmPayment` runs with `redirect: 'if_required'`, so the common case
 * never leaves the page.  A method that insists on a redirect comes back to
 * `return_url`, where `<CheckoutReturn/>` finishes the job.
 */
import { Elements, PaymentElement, useElements, useStripe } from '@stripe/react-stripe-js';
import { loadStripe } from '@stripe/stripe-js';
import type { Appearance, Stripe, StripeError } from '@stripe/stripe-js';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import type { CheckoutRequest } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { formatCents } from '@/portal/components/Money';
import { useDebounced } from '@/portal/components/useDebounced';
import type { CheckoutFields } from './api';
import { checkoutRequest, isAbortError, panelErrorMessage } from './api';
import { PORTAL_ENDPOINTS } from './endpoints';
import type { PaymentEndpoints } from './endpoints';
import type { ProviderPanelProps } from './types';

/** Stripe.js is a singleton per publishable key. */
const stripeByKey = new Map<string, Promise<Stripe | null>>();

/** The shared Stripe.js instance for `publishableKey`, loaded at most once. */
export function stripeFor(publishableKey: string): Promise<Stripe | null> {
  const existing = stripeByKey.get(publishableKey);
  if (existing) return existing;
  const created = loadStripe(publishableKey);
  stripeByKey.set(publishableKey, created);
  return created;
}

function cssToken(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

/** Dress the Payment Element in our own tokens rather than Stripe's defaults. */
export function appearanceFromTokens(): Appearance {
  return {
    theme: 'stripe',
    variables: {
      colorPrimary: cssToken('--color-primary', '#1f4e79'),
      colorBackground: cssToken('--color-bg-raised', '#ffffff'),
      colorText: cssToken('--color-fg', '#1d2530'),
      colorTextSecondary: cssToken('--color-muted', '#55606d'),
      colorDanger: cssToken('--color-bad', '#b3261e'),
      fontFamily: cssToken('--font-body', 'IBM Plex Sans, system-ui, sans-serif'),
      fontSizeBase: '1rem',
      borderRadius: cssToken('--radius', '6px'),
      spacingUnit: '4px',
    },
    rules: {
      '.Input': {
        border: `1px solid ${cssToken('--color-rule-strong', '#8c97a5')}`,
        boxShadow: 'none',
      },
      '.Input:focus': {
        border: `1px solid ${cssToken('--color-primary', '#1f4e79')}`,
        boxShadow: 'none',
        outline: `2px solid ${cssToken('--color-focus', '#1f4e79')}`,
      },
      '.Label': {
        fontWeight: '500',
        color: cssToken('--color-fg', '#1d2530'),
      },
    },
  };
}

/** Wait for the member to stop changing the amount before re-creating an intent. */
export const AMOUNT_DEBOUNCE_MS = 500;

/**
 * The checkout request for the current selection, once that selection has held still.
 *
 * The request travels through `useDebounced` as its own JSON, so a selection that
 * wanders and comes back to where it started settles on a value the panel already
 * holds and asks for no second PaymentIntent.  The object handed back keeps its
 * identity for as long as the JSON does, which is what lets the caller depend on it
 * and nothing else.
 */
function useSettledCheckout(fields: CheckoutFields): CheckoutRequest {
  const wanted = JSON.stringify(checkoutRequest(fields, 'stripe'));
  const settled = useDebounced(wanted, AMOUNT_DEBOUNCE_MS);
  return useMemo(() => JSON.parse(settled) as CheckoutRequest, [settled]);
}

interface Intent {
  paymentId: number;
  clientSecret: string;
}

export interface StripePanelProps extends ProviderPanelProps {
  publishableKey: string;
}

/** Creates a PaymentIntent for the current amount, then mounts the Payment Element. */
export function StripePanel({
  publishableKey,
  amountCents,
  onSuccess: handleSuccess,
  onRenewalContribution,
  endpoints = PORTAL_ENDPOINTS,
  ...fields
}: StripePanelProps): JSX.Element {
  const [intent, setIntent] = useState<Intent | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Each decline asks for a PaymentIntent of its own: the server cancels a declined
  // intent, so its client secret takes no second card.  The reason stays on screen
  // over the fresh form.
  const [attempt, setAttempt] = useState(0);
  const [declined, setDeclined] = useState<string | null>(null);
  const settled = useSettledCheckout(fields);

  const stripePromise = useMemo(() => stripeFor(publishableKey), [publishableKey]);
  const appearance = useMemo(() => appearanceFromTokens(), []);

  useEffect(() => {
    const controller = new AbortController();
    setIntent(null);
    setError(null);

    endpoints
      .createCheckout(settled, controller.signal)
      .then((checkout) => {
        if (controller.signal.aborted) return;
        if (checkout.provider !== 'stripe' || !checkout.client.client_secret) {
          setError("Stripe didn't start the payment. Try again in a moment.");
          return;
        }
        setIntent({ paymentId: checkout.payment_id, clientSecret: checkout.client.client_secret });
      })
      .catch((caught: unknown) => {
        if (isAbortError(caught) || controller.signal.aborted) return;
        setError(
          panelErrorMessage(caught, 'Could not start a Stripe payment.', onRenewalContribution),
        );
      });

    // Abandon the request rather than only ignore its answer. A StrictMode remount
    // aborts before `fetch` dispatches, so it creates one PaymentIntent, not two. A
    // debounced amount change re-runs the effect long after the first request went out:
    // that intent exists, and is left unconfirmed rather than charged.
    return () => {
      controller.abort();
    };
  }, [settled, onRenewalContribution, endpoints, attempt]);

  function handleDecline(message: string): void {
    setDeclined(message);
    setAttempt((count) => count + 1);
  }

  if (error) {
    return (
      <div className="checkout__panel">
        <p className="checkout__error" role="alert">
          {error}
        </p>
      </div>
    );
  }

  if (!intent) {
    return (
      <div className="checkout__panel">
        <p className="muted" role="status">
          Preparing secure payment…
        </p>
      </div>
    );
  }

  return (
    <div className="checkout__panel">
      <Elements
        // The attempt as well as the secret, so the form after a decline always starts
        // afresh with the reason on screen.
        key={`${attempt}:${intent.clientSecret}`}
        stripe={stripePromise}
        options={{ clientSecret: intent.clientSecret, appearance }}
      >
        <StripeForm
          paymentId={intent.paymentId}
          amountCents={amountCents}
          endpoints={endpoints}
          declined={declined}
          onSuccess={handleSuccess}
          onDecline={handleDecline}
        />
      </Elements>
    </div>
  );
}

interface StripeFormProps {
  paymentId: number;
  amountCents: number;
  endpoints: PaymentEndpoints;
  /** Why the last payment was declined, shown until the next try; null for none. */
  declined: string | null;
  onSuccess: ProviderPanelProps['onSuccess'];
  /** Called with Stripe's reason when a payment is declined, to start another. */
  onDecline: (message: string) => void;
}

/**
 * Whether Stripe's `error` is a decline, after which the intent is finished with.
 *
 * Only a refused card (`card_error`), or an intent Stripe hands back waiting for
 * another method, counts. Any other error, such as a dropped connection or a fault at
 * Stripe, may have come after the money moved, so the same intent has to be kept:
 * starting another could take the money twice.
 *
 * @param error What `confirmPayment` or `confirmSetup` answered with.
 * @returns True when a fresh intent is the way to try again.
 */
export function isStripeDecline(error: StripeError): boolean {
  return (
    error.type === 'card_error' ||
    error.payment_intent?.status === 'requires_payment_method' ||
    error.setup_intent?.status === 'requires_payment_method'
  );
}

/** The Payment Element plus its submit button, confirming the intent on submit. */
function StripeForm({
  paymentId,
  amountCents,
  endpoints,
  declined,
  onSuccess,
  onDecline,
}: StripeFormProps): JSX.Element {
  const stripe = useStripe();
  const elements = useElements();
  const [error, setError] = useState<string | null>(declined);
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  /**
   * Have the server ask Stripe about a declined intent, which fails the payment and
   * cancels the intent there without waiting for the webhook.  The answer is not
   * needed: the decline is already known, and a fresh payment follows either way.
   */
  async function reportDecline(intentId: string): Promise<void> {
    try {
      await endpoints.confirmStripe(paymentId, intentId);
    } catch {
      // The webhook reports the same decline, so a failure here costs nothing.
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!stripe || !elements) return;

    setBusy(true);
    setError(null);
    try {
      const confirmation = await stripe.confirmPayment({
        elements,
        confirmParams: { return_url: endpoints.stripeReturnUrl(paymentId) },
        redirect: 'if_required',
      });

      if (confirmation.error) {
        const message = confirmation.error.message ?? 'That payment could not be completed.';
        if (!isStripeDecline(confirmation.error)) {
          setError(message);
          return;
        }
        await reportDecline(confirmation.error.payment_intent?.id ?? '');
        onDecline(message);
        return;
      }

      const intentId = confirmation.paymentIntent?.id ?? '';
      const result = await endpoints.confirmStripe(paymentId, intentId);
      if (result.status === 'succeeded') {
        onSuccess({ paymentId, membership: result.membership });
        return;
      }
      setError("Stripe hasn't confirmed that payment yet. Try again in a moment.");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : 'That payment could not be completed.',
      );
    } finally {
      if (mounted.current) setBusy(false);
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
      <Button type="submit" disabled={!stripe || busy}>
        {busy ? 'Processing…' : `Pay ${formatCents(amountCents)}`}
      </Button>
      <p className="checkout__fineprint muted">
        Card details go straight to Stripe; CalDART never sees them. Apple Pay and Google Pay appear
        above when your browser offers them.
      </p>
    </form>
  );
}
