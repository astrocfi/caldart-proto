/**
 * Step 4 — pay, or, for a friend, contribute.
 *
 * The payment UI itself is `<Checkout/>` from `@/portal/features/checkout`:
 * it offers the plans, the optional contribution and the card / Apple Pay /
 * Google Pay / PayPal buttons, then calls `onSuccess` once the server has
 * activated the membership.  The step shows the kind the wizard names in
 * `joiningAs`, which starts as the kind the visitor chose when they registered.
 *
 * A friend owes no dues, so a friend's step offers a contribution alone, and its
 * **Not now** button moves on without paying.  Under the contribution, **I changed
 * my mind, I want to be a member** swaps the step to a member's: nothing changes on
 * the server until a membership is paid for.  A member's step has no **Not now**:
 * paying is what makes a member.  Its one other way on is the card for changing
 * one's mind, chosen like a plan: the contribution stays under it, and paying one, or
 * **Continue as a friend** without one, makes the account a friend and moves on.
 */
import { Checkout } from '@/portal/features/checkout';
import type { CheckoutResult } from '@/portal/features/checkout';
import { useQueryClient } from '@tanstack/react-query';
import type { JSX } from 'react';

import type { PersonKind } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import { refreshAfterPayment } from './refresh';
import { joinStepEyebrow } from './steps';
import './join.css';

export interface PayStepProps {
  /** The kind of account the step is for: a member pays dues, a friend may contribute. */
  joiningAs: PersonKind;
  /** Called when the visitor changes their mind, with the kind they chose instead. */
  onJoiningAsChange: (kind: PersonKind) => void;
  /** Called when a payment settles, before `onDone`; skipping does not call it. */
  onPaid: () => void;
  /** Called to move on, after a payment or a friend's **Not now**. */
  onDone: () => void;
}

/** Step 4 of the join wizard: dues through `<Checkout/>`, or a friend's contribution. */
export function PayStep({
  joiningAs,
  onJoiningAsChange: handleJoiningAsChange,
  onPaid: handlePaid,
  onDone: handleDone,
}: PayStepProps): JSX.Element {
  const queryClient = useQueryClient();

  function handleSuccess(_result: CheckoutResult) {
    // Membership, payment history, and `profile_complete`/`membership` on the
    // user payload have all just moved.
    refreshAfterPayment(queryClient);
    handlePaid();
    handleDone();
  }

  // Each card is keyed by its kind, so switching starts the checkout afresh rather
  // than carrying the other kind's choices over.
  if (joiningAs === 'friend') {
    return (
      <Card
        key="friend"
        className="join-card"
        eyebrow={joinStepEyebrow('pay')}
        title="Contribute to CalDART"
      >
        <p className="muted">
          Friends pay no dues. A contribution of any size helps, and you can skip this step if now
          is not the time.
        </p>
        <Checkout
          mode="contribute"
          onSuccess={handleSuccess}
          onSkip={handleDone}
          onBecomeMember={() => handleJoiningAsChange('member')}
        />
      </Card>
    );
  }

  return (
    <Card key="member" className="join-card" eyebrow={joinStepEyebrow('pay')} title="Pay your dues">
      <p className="muted">
        Membership starts the moment the payment clears. You can add a contribution on top if you
        would like to support CalDART further.
      </p>
      <Checkout
        mode="join"
        onSuccess={handleSuccess}
        onBecomeFriend={() => handleJoiningAsChange('friend')}
        onFriendDone={handleDone}
      />
    </Card>
  );
}
