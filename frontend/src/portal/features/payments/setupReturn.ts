/**
 * Finishing a setup the member was sent away from.
 *
 * A payment method that needs the bank's own page cannot be confirmed where it
 * was collected: Stripe sends the browser to its bank and then back to
 * `/portal/payments` with the SetupIntent named in the query string.  Nothing
 * else on the screen would notice, so the mandate would sit `pending` and the
 * member would be told renewal is off even though they saved a method.
 */
import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import { useConfirmRenewal } from './api';

/** What Stripe appends to the return URL once the bank has answered. */
const RETURN_PARAMS = ['setup_intent', 'setup_intent_client_secret', 'redirect_status'] as const;

export interface SetupReturn {
  /** True while the returned SetupIntent is being confirmed with CalDART. */
  isConfirming: boolean;
  /** Why the returned SetupIntent was refused, or `null`. */
  error: string | null;
}

/**
 * Confirm the SetupIntent named in the query string, once, on return.
 *
 * The parameters are dropped from the address afterwards, whether the
 * confirmation was accepted or refused, so a reload does not send it again.
 * A visit carrying no `setup_intent` does nothing at all.
 */
export function useSetupReturn(): SetupReturn {
  const [params, setParams] = useSearchParams();
  const confirm = useConfirmRenewal();
  const [error, setError] = useState<string | null>(null);
  const confirmed = useRef<string | null>(null);

  const setupIntentId = params.get(RETURN_PARAMS[0]);
  const { mutateAsync } = confirm;

  useEffect(() => {
    if (setupIntentId === null || confirmed.current === setupIntentId) return;
    confirmed.current = setupIntentId;

    void mutateAsync({ setup_intent_id: setupIntentId, setup_token: '' })
      .catch((caught: unknown) => {
        setError(
          caught instanceof ApiError
            ? caught.message
            : 'That payment method could not be saved. Please try again.',
        );
      })
      .finally(() => {
        setParams(
          (current) => {
            const next = new URLSearchParams(current);
            for (const name of RETURN_PARAMS) next.delete(name);
            return next;
          },
          { replace: true },
        );
      });
  }, [setupIntentId, mutateAsync, setParams]);

  return { isConfirming: confirm.isPending, error };
}
