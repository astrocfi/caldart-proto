/**
 * The landing pad for redirect-based payment methods.
 *
 * Some methods (3-D Secure, bank redirects) take the browser away from the
 * page and send it back to `return_url` with `payment_id` and
 * `payment_intent` in the query string.  We confirm with our server, then
 * poll until the payment settles, because a redirect method can still be
 * `processing` for a second or two after the browser returns.
 *
 * `routes/join.tsx` renders this at `/join/done`.
 */
import { useEffect, useState } from 'react';
import type { JSX, ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import { EmptyState } from '@/portal/components/EmptyState';
import { PORTAL_ENDPOINTS } from './endpoints';
import type { PaymentEndpoints } from './endpoints';
import type { CheckoutResult } from './types';

/** How long to keep asking before giving up, and how often. */
export const POLL_TIMEOUT_MS = 10_000;
export const POLL_INTERVAL_MS = 1_000;

export interface CheckoutReturnProps {
  onSuccess: (result: CheckoutResult) => void;
  /**
   * Offered beneath the message when the payment cannot be confirmed — the
   * join wizard puts a way back to the payment step there, so a declined card
   * is not a dead end.
   */
  action?: ReactNode;
}

/** Wait `ms`, or stop waiting the moment `signal` aborts. */
function sleep(ms: number, signal: AbortSignal): Promise<void> {
  if (signal.aborted) return Promise.resolve();
  return new Promise((resolve) => {
    const finish = (): void => {
      window.clearTimeout(timer);
      signal.removeEventListener('abort', finish);
      resolve();
    };
    const timer = window.setTimeout(finish, ms);
    signal.addEventListener('abort', finish);
  });
}

/** Confirms a redirect-based payment, polling until it settles or fails. */
export function CheckoutReturn({ onSuccess, action }: CheckoutReturnProps): JSX.Element {
  const [params] = useSearchParams();
  const error = useSettledPayment({
    paymentId: Number.parseInt(params.get('payment_id') ?? '', 10),
    paymentIntentId: params.get('payment_intent') ?? '',
    endpoints: PORTAL_ENDPOINTS,
    onSuccess,
  });

  if (error) {
    return <EmptyState title="Payment not confirmed" description={error} action={action} />;
  }

  return (
    <p className="muted" role="status" aria-live="polite">
      Confirming your payment…
    </p>
  );
}

export interface SettledPaymentOptions {
  /** The payment the browser came back for; `NaN` when the link carried none. */
  paymentId: number;
  /** Stripe's intent, as the redirect named it; empty when it named none. */
  paymentIntentId: string;
  /** The calls that confirm and read the payment. */
  endpoints: PaymentEndpoints;
  onSuccess: (result: CheckoutResult) => void;
}

/**
 * Confirm a payment a redirect method has sent the browser back for, then poll until
 * it settles.
 *
 * Calls `onSuccess` once the payment has succeeded, and answers the sentence to show
 * when it cannot be confirmed (declined, still processing after `POLL_TIMEOUT_MS`, or
 * a link with no payment), or null while it is still being confirmed.
 */
export function useSettledPayment({
  paymentId,
  paymentIntentId,
  endpoints,
  onSuccess,
}: SettledPaymentOptions): string | null {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(paymentId)) {
      setError('That link is missing a payment reference.');
      return;
    }

    // Every run owns its requests and its wait, so a run that is torn down takes
    // them with it and the run that replaces it starts from nothing.
    const controller = new AbortController();
    const { signal } = controller;

    async function settle(): Promise<void> {
      // The confirm call is what actually activates the membership; a failure
      // here is not fatal, because the webhook may have got there first.
      try {
        const confirmed = await endpoints.confirmStripe(paymentId, paymentIntentId, signal);
        if (signal.aborted) return;
        if (confirmed.status === 'succeeded') {
          onSuccess({ paymentId, membership: confirmed.membership });
          return;
        }
      } catch {
        // fall through to polling
      }

      const deadline = Date.now() + POLL_TIMEOUT_MS;
      while (!signal.aborted && Date.now() < deadline) {
        try {
          const result = await endpoints.fetchPayment(paymentId, signal);
          if (signal.aborted) return;
          if (result.status === 'succeeded') {
            onSuccess({ paymentId, membership: result.membership });
            return;
          }
          if (result.status === 'failed') {
            setError('That payment was declined. Nothing was charged.');
            return;
          }
        } catch (caught) {
          if (signal.aborted) return;
          setError(
            caught instanceof ApiError ? caught.message : 'We could not check that payment.',
          );
          return;
        }
        await sleep(POLL_INTERVAL_MS, signal);
      }

      if (!signal.aborted) {
        setError(
          'Your payment is still being processed. It is safe to close this page — we will email ' +
            'you when it clears, and your membership page will update on its own.',
        );
      }
    }

    void settle();
    return () => {
      controller.abort();
    };
  }, [paymentId, paymentIntentId, endpoints, onSuccess]);

  return error;
}
