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
import type { MandateScope } from '@/portal/api/queries';
import { useConfirmRenewal } from './api';

/** The query parameter the return URL names the authority in; absent means the renewal. */
export const SETUP_SCOPE_PARAM = 'mandate';

/** What Stripe appends to the return URL once the bank has answered, and our own scope. */
const RETURN_PARAMS = [
  'setup_intent',
  'setup_intent_client_secret',
  'redirect_status',
  SETUP_SCOPE_PARAM,
] as const;

export interface SetupReturn {
  /** True while the returned SetupIntent is being confirmed with CalDART. */
  isConfirming: boolean;
  /** Why the returned SetupIntent was refused, or `null`. */
  error: string | null;
}

/**
 * Confirm the SetupIntent named in the query string, once, on return.
 *
 * Only the card for the authority the return names acts on it: the recurring
 * donation's when the address carries `mandate=donation`, the renewal's otherwise.
 * The parameters are dropped from the address afterwards, whether the
 * confirmation was accepted or refused, so a reload does not send it again.
 * A visit carrying no `setup_intent` does nothing at all.
 */
export function useSetupReturn(scope: MandateScope): SetupReturn {
  const [params, setParams] = useSearchParams();
  const confirm = useConfirmRenewal(scope);
  const [error, setError] = useState<string | null>(null);
  const confirmed = useRef<string | null>(null);

  const returnedScope = params.get(SETUP_SCOPE_PARAM) ?? 'renewal';
  const setupIntentId = returnedScope === scope ? params.get(RETURN_PARAMS[0]) : null;
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
