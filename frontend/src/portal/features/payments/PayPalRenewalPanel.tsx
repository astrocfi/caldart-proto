/**
 * PayPal's buttons, approving a vault setup token rather than a payment.
 *
 * `createVaultSetupToken` asks our server for the token, because the vault it
 * belongs to is CalDART's; approving it in PayPal's window gives permission for
 * later charges, and our server exchanges the approved token for the payment
 * token it keeps.  Nothing is charged today.
 */
import { PayPalButtons, PayPalScriptProvider } from '@paypal/react-paypal-js';
import { useRef, useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import { useToast } from '@/portal/components/Toast';
import { useConfirmRenewal, useStartRenewalSetup } from './api';
import type { RenewalPanelProps } from './types';

/** What a member is told when they close PayPal's window without approving. */
const SETUP_CANCELED = 'Setup canceled';

export interface PayPalRenewalPanelProps extends RenewalPanelProps {
  clientId: string;
}

/** PayPal's buttons over a vault setup token, saving the account for later charges. */
export function PayPalRenewalPanel({
  clientId,
  plan,
  contributionCents,
  onDone: handleDone,
}: PayPalRenewalPanelProps): JSX.Element {
  const [error, setError] = useState<string | null>(null);
  const setupToken = useRef<string | null>(null);
  // The SDK hands a `createVaultSetupToken` rejection to `onError`, which would
  // otherwise replace the server's reason with the generic notice.
  const hasSetupError = useRef(false);
  const start = useStartRenewalSetup();
  const confirm = useConfirmRenewal();
  const toast = useToast();

  return (
    <div className="checkout__panel stack">
      {error ? (
        <p className="checkout__error" role="alert">
          {error}
        </p>
      ) : null}

      <PayPalScriptProvider
        options={{ clientId, currency: 'USD', intent: 'capture', components: 'buttons' }}
      >
        <PayPalButtons
          style={{ layout: 'vertical', shape: 'rect', label: 'paypal' }}
          forceReRender={[plan, contributionCents]}
          createVaultSetupToken={async () => {
            setError(null);
            hasSetupError.current = false;
            try {
              const response = await start.mutateAsync({
                plan,
                contribution_cents: contributionCents,
                provider: 'paypal',
              });
              if (response.provider !== 'paypal' || !response.client.setup_token) {
                throw new Error('PayPal did not return a setup token.');
              }
              setupToken.current = response.client.setup_token;
              return response.client.setup_token;
            } catch (caught) {
              hasSetupError.current = true;
              setError(
                caught instanceof ApiError
                  ? caught.message
                  : 'PayPal could not start saving that account.',
              );
              throw caught;
            }
          }}
          onApprove={async () => {
            const token = setupToken.current;
            if (token === null) {
              setError('That PayPal setup has gone missing. Please try again.');
              return;
            }
            try {
              await confirm.mutateAsync({ setup_intent_id: '', setup_token: token });
              handleDone();
            } catch (caught) {
              setError(
                caught instanceof ApiError
                  ? caught.message
                  : 'That PayPal account could not be saved.',
              );
            }
          }}
          onCancel={() => toast.show(SETUP_CANCELED)}
          onError={() => {
            if (hasSetupError.current) {
              hasSetupError.current = false;
              return;
            }
            setError('PayPal could not be reached. Please try again.');
          }}
        />
      </PayPalScriptProvider>

      <p className="checkout__fineprint muted">
        You will be asked to sign in to PayPal in a secure window. Nothing is charged today; the
        account is saved so next year&rsquo;s dues can be taken from it.
      </p>
    </div>
  );
}
