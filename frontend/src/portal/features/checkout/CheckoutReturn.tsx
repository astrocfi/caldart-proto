/**
 * The landing pad for redirect-based payment methods (PLAN §10).
 *
 * Some methods (3-D Secure, bank redirects) take the browser away from the
 * page and send it back to `return_url` with `payment_id` and
 * `payment_intent` in the query string.  We confirm with our server, then
 * poll until the payment settles, because a redirect method can still be
 * `processing` for a second or two after the browser returns.
 *
 * `routes/join.tsx` renders this at `/join/done`.
 */
import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { ApiError } from '../../api/client';
import { EmptyState } from '../../components/EmptyState';
import { confirmStripePayment, fetchPayment } from './api';
import type { CheckoutResult } from './types';

/** How long to keep asking before giving up, and how often. */
export const POLL_TIMEOUT_MS = 10_000;
export const POLL_INTERVAL_MS = 1_000;

export interface CheckoutReturnProps {
  onSuccess: (result: CheckoutResult) => void;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export function CheckoutReturn({ onSuccess }: CheckoutReturnProps) {
  const [params] = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  const paymentId = Number.parseInt(params.get('payment_id') ?? '', 10);
  const paymentIntentId = params.get('payment_intent') ?? '';

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    if (!Number.isFinite(paymentId)) {
      setError('That link is missing a payment reference.');
      return;
    }

    let cancelled = false;

    async function settle() {
      // The confirm call is what actually activates the membership; a failure
      // here is not fatal, because the webhook may have got there first.
      try {
        const confirmed = await confirmStripePayment(paymentId, paymentIntentId);
        if (!cancelled && confirmed.status === 'succeeded') {
          onSuccess({ paymentId, membership: confirmed.membership });
          return;
        }
      } catch {
        // fall through to polling
      }

      const deadline = Date.now() + POLL_TIMEOUT_MS;
      while (!cancelled && Date.now() < deadline) {
        try {
          const result = await fetchPayment(paymentId);
          if (cancelled) return;
          if (result.status === 'succeeded') {
            onSuccess({ paymentId, membership: result.membership });
            return;
          }
          if (result.status === 'failed') {
            setError('That payment was declined. Nothing was charged.');
            return;
          }
        } catch (caught) {
          if (cancelled) return;
          setError(
            caught instanceof ApiError ? caught.message : 'We could not check that payment.',
          );
          return;
        }
        await sleep(POLL_INTERVAL_MS);
      }

      if (!cancelled) {
        setError(
          'Your payment is still being processed. It is safe to close this page — we will email ' +
            'you when it clears, and your membership page will update on its own.',
        );
      }
    }

    void settle();
    return () => {
      cancelled = true;
    };
  }, [paymentId, paymentIntentId, onSuccess]);

  if (error) {
    return <EmptyState title="Payment not confirmed" description={error} />;
  }

  return (
    <p className="muted" role="status" aria-live="polite">
      Confirming your payment…
    </p>
  );
}
