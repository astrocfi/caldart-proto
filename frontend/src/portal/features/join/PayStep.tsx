/**
 * Step 3 — pay.
 *
 * The payment UI itself is `<Checkout/>` from `@/portal/features/checkout`:
 * it offers the plans, the optional contribution and the card / Apple Pay /
 * Google Pay / PayPal buttons, then calls `onSuccess` once the server has
 * activated the membership.
 */
import { Checkout } from '@/portal/features/checkout';
import type { CheckoutResult } from '@/portal/features/checkout';
import { useQueryClient } from '@tanstack/react-query';
import type { JSX } from 'react';

import { Card } from '@/portal/components/Card';
import { refreshAfterPayment } from './refresh';
import { joinStepEyebrow } from './steps';
import './join.css';

export interface PayStepProps {
  onDone: () => void;
}

/** Step 3 of the join wizard: collects payment through `<Checkout/>`. */
export function PayStep({ onDone }: PayStepProps): JSX.Element {
  const queryClient = useQueryClient();

  function handleSuccess(_result: CheckoutResult) {
    // Membership, payment history, and `profile_complete`/`membership` on the
    // user payload have all just moved.
    refreshAfterPayment(queryClient);
    onDone();
  }

  return (
    <Card className="join-card" eyebrow={joinStepEyebrow('pay')} title="Pay your dues">
      <p className="muted">
        Membership starts the moment the payment clears. You can add a contribution on top if you
        would like to support CalDART further.
      </p>
      <Checkout mode="join" onSuccess={handleSuccess} />
    </Card>
  );
}
