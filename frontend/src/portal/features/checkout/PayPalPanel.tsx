/**
 * PayPal's buttons.
 *
 * `createOrder` asks our server for an order, because the amount must be the
 * one the server computed; `onApprove` asks our server to capture it, because
 * a capture is the only thing that proves the money moved.
 */
import { PayPalButtons, PayPalScriptProvider } from '@paypal/react-paypal-js';
import { useRef, useState } from 'react';
import type { JSX } from 'react';

import { ApiError } from '../../api/client';
import { capturePayPalOrder, createCheckout } from './api';
import type { ProviderPanelProps } from './types';

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
            const checkout = await createCheckout({
              plan,
              contribution_cents: contributionCents,
              provider: 'paypal',
            });
            paymentId.current = checkout.payment_id;
            const orderId = checkout.client.order_id;
            if (!orderId) throw new Error('PayPal did not return an order.');
            return orderId;
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
          onError={() => setError('PayPal could not be reached. Please try again.')}
        />
      </PayPalScriptProvider>

      <p className="checkout__fineprint muted">
        You will be asked to sign in to PayPal in a secure window. Your membership starts the moment
        the payment clears.
      </p>
    </div>
  );
}
