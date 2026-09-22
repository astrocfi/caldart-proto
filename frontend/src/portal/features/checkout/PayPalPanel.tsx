/**
 * PayPal's buttons.
 *
 * `createOrder` asks our server for an order, because the amount must be the
 * one the server computed; `onApprove` asks our server to capture it, because
 * a capture is the only thing that proves the money moved.  A refusal from our
 * server is shown in the panel's own alert; closing PayPal's window without
 * paying raises a toast and leaves the checkout exactly as it was.
 */
import { PayPalButtons, PayPalScriptProvider } from '@paypal/react-paypal-js';
import { useRef, useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '@/portal/api/client';
import { useToast } from '@/portal/components/Toast';
import { capturePayPalOrder, createCheckout } from './api';
import type { ProviderPanelProps } from './types';

/** What a member is told when they close PayPal's window without paying. */
const PAYMENT_CANCELED = 'Payment canceled';

export interface PayPalPanelProps extends ProviderPanelProps {
  clientId: string;
}

/** PayPal's buttons: creates an order on our server, then captures it. */
export function PayPalPanel({
  clientId,
  plan,
  contributionCents,
  amountCents,
  onSuccess,
}: PayPalPanelProps): JSX.Element {
  const [error, setError] = useState<string | null>(null);
  const paymentId = useRef<number | null>(null);
  // The SDK hands a `createOrder` rejection to `onError`, which would otherwise
  // replace the server's reason with the generic notice.
  const hasOrderError = useRef(false);
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
          forceReRender={[amountCents, plan]}
          createOrder={async () => {
            setError(null);
            hasOrderError.current = false;
            try {
              const checkout = await createCheckout({
                plan,
                contribution_cents: contributionCents,
                provider: 'paypal',
              });
              paymentId.current = checkout.payment_id;
              if (checkout.provider !== 'paypal' || !checkout.client.order_id) {
                throw new Error('PayPal did not return an order.');
              }
              return checkout.client.order_id;
            } catch (caught) {
              // PayPal's own error panel says nothing about why, so the server's
              // reason is put on screen here before the rejection goes back to it.
              hasOrderError.current = true;
              setError(
                caught instanceof ApiError
                  ? caught.message
                  : 'That PayPal payment could not be started.',
              );
              throw caught;
            }
          }}
          onApprove={async (data) => {
            const id = paymentId.current;
            if (id === null) {
              setError('That PayPal order has gone missing. Please try again.');
              return;
            }
            try {
              const result = await capturePayPalOrder(id, data.orderID);
              if (result.status === 'succeeded') {
                onSuccess({ paymentId: id, membership: result.membership });
                return;
              }
              setError('PayPal did not complete that payment. Nothing was charged.');
            } catch (caught) {
              setError(
                caught instanceof ApiError
                  ? caught.message
                  : 'That PayPal payment could not be completed.',
              );
            }
          }}
          onCancel={() => toast.show(PAYMENT_CANCELED)}
          onError={() => {
            if (hasOrderError.current) {
              hasOrderError.current = false;
              return;
            }
            setError('PayPal could not be reached. Please try again.');
          }}
        />
      </PayPalScriptProvider>

      <p className="checkout__fineprint muted">
        You will be asked to sign in to PayPal in a secure window. Your membership starts the moment
        the payment clears.
      </p>
    </div>
  );
}
