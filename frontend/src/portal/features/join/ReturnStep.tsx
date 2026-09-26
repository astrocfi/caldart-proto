/**
 * The landing pad for a payment method that took the browser away.
 *
 * Stripe's `return_url` is `/portal/join/done?payment_id=…&payment_intent=…`,
 * so a 3-D Secure card or a redirecting wallet comes back *here* rather than
 * to the pay step.  `<CheckoutReturn/>` confirms with our server and polls
 * until the payment settles; only then does the wizard show step 4.
 */
import { CheckoutReturn } from '@/portal/features/checkout';
import type { CheckoutResult } from '@/portal/features/checkout';
import type { JSX } from 'react';

import { ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { joinStepEyebrow } from './steps';
import './join.css';

export interface ReturnStepProps {
  onSettled: (result: CheckoutResult) => void;
}

/** Confirms a redirect-based payment method and settles it via `<CheckoutReturn/>`. */
export function ReturnStep({ onSettled: handleSettled }: ReturnStepProps): JSX.Element {
  return (
    <Card className="join-card" eyebrow={joinStepEyebrow('pay')} title="Finishing your payment">
      <CheckoutReturn
        onSuccess={handleSettled}
        action={
          <ButtonLink to="/join/pay" variant="secondary">
            Back to payment
          </ButtonLink>
        }
      />
    </Card>
  );
}
