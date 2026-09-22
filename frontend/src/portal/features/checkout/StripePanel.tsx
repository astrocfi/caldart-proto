/**
 * Stripe's Payment Element.
 *
 * Card, Apple Pay, Google Pay and Link all arrive through this one element:
 * the server enabled `automatic_payment_methods`, so Stripe shows whichever
 * the browser and the account support.  Opening the tab creates the
 * PaymentIntent; changing the amount afterwards quietly creates a new one.
 *
 * `confirmPayment` runs with `redirect: 'if_required'`, so the common case
 * never leaves the page.  A method that insists on a redirect comes back to
 * `return_url`, where `<CheckoutReturn/>` finishes the job.
 */
import { Elements, PaymentElement, useElements, useStripe } from '@stripe/react-stripe-js';
import { loadStripe } from '@stripe/stripe-js';
import type { Appearance, Stripe } from '@stripe/stripe-js';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '../../api/client';
import type { CheckoutRequest } from '../../api/types';
import { Button } from '../../components/Button';
import { formatCents } from '../../components/Money';
import { useDebounced } from '../../components/useDebounced';
import { confirmStripePayment, createCheckout, isAbortError } from './api';
import type { ProviderPanelProps } from './types';

/** Stripe.js is a singleton per publishable key. */
const stripeByKey = new Map<string, Promise<Stripe | null>>();

/** The shared Stripe.js instance for `publishableKey`, loaded at most once. */
function stripeFor(publishableKey: string): Promise<Stripe | null> {
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
function appearanceFromTokens(): Appearance {
  return {
    theme: 'stripe',
    variables: {
      colorPrimary: cssToken('--color-primary', '#1f4d3a'),
      colorBackground: cssToken('--color-bg-raised', '#fbfaf6'),
      colorText: cssToken('--color-fg', '#1b1f24'),
      colorTextSecondary: cssToken('--color-muted', '#6b6f76'),
      colorDanger: cssToken('--color-bad', '#b23a2b'),
      fontFamily: cssToken('--font-body', 'IBM Plex Sans, system-ui, sans-serif'),
      fontSizeBase: '1rem',
      borderRadius: cssToken('--radius', '2px'),
      spacingUnit: '4px',
    },
    rules: {
      '.Input': {
        border: `1px solid ${cssToken('--color-rule-strong', '#b9b1a0')}`,
        boxShadow: 'none',
      },
      '.Input:focus': {
        border: `1px solid ${cssToken('--color-primary', '#1f4d3a')}`,
        boxShadow: 'none',
        outline: `2px solid ${cssToken('--color-focus', '#1f4d3a')}`,
      },
      '.Label': {
        fontWeight: '500',
        color: cssToken('--color-fg', '#1b1f24'),
      },
    },
  };
}

/** Where Stripe sends the browser back for redirect-based methods. */
function returnUrl(paymentId: number): string {
  const origin = typeof window === 'undefined' ? '' : window.location.origin;
  return `${origin}/portal/join/done?payment_id=${paymentId}`;
}

/** Wait for the member to stop changing the amount before re-creating an intent. */
const AMOUNT_DEBOUNCE_MS = 500;

/**
 * The checkout request for the current selection, once that selection has held still.
 *
 * The request travels through `useDebounced` as its own JSON, so a selection that
 * wanders and comes back to where it started settles on a value the panel already
 * holds and asks for no second PaymentIntent.  The object handed back keeps its
 * identity for as long as the JSON does, which is what lets the caller depend on it
 * and nothing else.
 */
function useSettledCheckout(plan: string | null, contributionCents: number): CheckoutRequest {
  const wanted = JSON.stringify({
    plan,
    contribution_cents: contributionCents,
    provider: 'stripe',
  } satisfies CheckoutRequest);
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
  plan,
  contributionCents,
  amountCents,
  onSuccess,
}: StripePanelProps): JSX.Element {
  const [intent, setIntent] = useState<Intent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const settled = useSettledCheckout(plan, contributionCents);

  const stripePromise = useMemo(() => stripeFor(publishableKey), [publishableKey]);
  const appearance = useMemo(() => appearanceFromTokens(), []);

  useEffect(() => {
    const controller = new AbortController();
    setIntent(null);
    setError(null);

    createCheckout(settled, controller.signal)
      .then((checkout) => {
        if (controller.signal.aborted) return;
        const clientSecret = checkout.client.client_secret;
        if (!clientSecret) {
          setError('Stripe did not return a payment session. Please try again.');
          return;
        }
        setIntent({ paymentId: checkout.payment_id, clientSecret });
      })
      .catch((caught: unknown) => {
        if (isAbortError(caught) || controller.signal.aborted) return;
        setError(caught instanceof ApiError ? caught.message : 'Could not start a Stripe payment.');
      });

    // Abandon the request rather than only ignore its answer. A StrictMode remount
    // aborts before `fetch` dispatches, so it creates one PaymentIntent, not two. A
    // debounced amount change re-runs the effect long after the first request went out:
    // that intent exists, and is left unconfirmed rather than charged.
    return () => {
      controller.abort();
    };
  }, [settled]);

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
        key={intent.clientSecret}
        stripe={stripePromise}
        options={{ clientSecret: intent.clientSecret, appearance }}
      >
        <StripeForm paymentId={intent.paymentId} amountCents={amountCents} onSuccess={onSuccess} />
      </Elements>
    </div>
  );
}

interface StripeFormProps {
  paymentId: number;
  amountCents: number;
  onSuccess: ProviderPanelProps['onSuccess'];
}

/** The Payment Element plus its submit button, confirming the intent on submit. */
function StripeForm({ paymentId, amountCents, onSuccess }: StripeFormProps): JSX.Element {
  const stripe = useStripe();
  const elements = useElements();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!stripe || !elements) return;

    setBusy(true);
    setError(null);
    try {
      const confirmation = await stripe.confirmPayment({
        elements,
        confirmParams: { return_url: returnUrl(paymentId) },
        redirect: 'if_required',
      });

      if (confirmation.error) {
        setError(confirmation.error.message ?? 'That payment could not be completed.');
        return;
      }

      const intentId = confirmation.paymentIntent?.id ?? '';
      const result = await confirmStripePayment(paymentId, intentId);
      if (result.status === 'succeeded') {
        onSuccess({ paymentId, membership: result.membership });
        return;
      }
      setError('Stripe has not confirmed that payment yet. Please try again in a moment.');
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
