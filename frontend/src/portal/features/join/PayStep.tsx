/**
 * Step 4 — pay, or, for a friend, contribute.
 *
 * The payment UI itself is `<Checkout/>` from `@/portal/features/checkout`:
 * it offers the plans, the optional contribution and the card / Apple Pay /
 * Google Pay / PayPal buttons, then calls `onSuccess` once the server has
 * activated the membership.  A friend owes no dues, so a friend's step offers a
 * contribution alone, and its **Not now** button moves on without paying.
 */
import { Checkout } from '@/portal/features/checkout';
import type { CheckoutResult } from '@/portal/features/checkout';
import { useQueryClient } from '@tanstack/react-query';
import type { JSX } from 'react';

import { useAuth } from '@/portal/auth/useAuth';
import { Card } from '@/portal/components/Card';
import { refreshAfterPayment } from './refresh';
import { joinStepEyebrow, joiningAs } from './steps';
import './join.css';

export interface PayStepProps {
  onDone: () => void;
}

/** Step 4 of the join wizard: dues through `<Checkout/>`, or a friend's contribution. */
export function PayStep({ onDone }: PayStepProps): JSX.Element {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  function handleSuccess(_result: CheckoutResult) {
    // Membership, payment history, and `profile_complete`/`membership` on the
    // user payload have all just moved.
    refreshAfterPayment(queryClient);
    onDone();
  }

  if (joiningAs(user) === 'friend') {
    return (
      <Card className="join-card" eyebrow={joinStepEyebrow('pay')} title="Contribute to CalDART">
        <p className="muted">
          Friends pay no dues. A contribution of any size helps, and you can skip this step if now
          is not the time.
        </p>
        <Checkout mode="contribute" onSuccess={handleSuccess} onSkip={onDone} />
      </Card>
    );
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
