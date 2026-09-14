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

import { ButtonLink } from '../../components/Button';
import { Card } from '../../components/Card';
import './join.css';

export interface ReturnStepProps {
  onSettled: (result: CheckoutResult) => void;
}

export function ReturnStep({ onSettled }: ReturnStepProps) {
  return (
    <Card className="join-card" eyebrow="Step 3 of 4" title="Finishing your payment">
      <CheckoutReturn
        onSuccess={onSettled}
        action={
          <ButtonLink to="/join/pay" variant="secondary">
            Back to payment
          </ButtonLink>
        }
      />
    </Card>
  );
}
