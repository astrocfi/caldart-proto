/**
 * Step 4 — pay, or, for a friend, donate.
 *
 * The payment UI itself is `<Checkout/>` from `@/portal/features/checkout`:
 * it offers the plans, the optional contribution and the card / Apple Pay /
 * Google Pay / PayPal buttons, then calls `onSuccess` once the server has
 * activated the membership.  The step's card holds the checkout directly, under the
 * step's own heading.  The step shows the kind the wizard names in `joiningAs`, which
 * starts as the kind the visitor chose when they registered.
 *
 * A friend owes no dues, so a friend's step offers a donation alone, and its
 * **Continue without a gift** button moves on without paying.  Under the donation,
 * **I changed my mind, I want to be a member** swaps the step to a member's: nothing
 * changes on the server until a membership is paid for.  A member's step has no way
 * past paying but one: **Join as a friend instead (no dues)** under the plans swaps the
 * step to a friend's.  An account the server still holds as a member is made a friend
 * (`POST /me/kind/friend`) as it leaves a friend's step, by a donation or without one.
 */
import { Checkout } from '@/portal/features/checkout';
import type { CheckoutResult } from '@/portal/features/checkout';
import { useQueryClient } from '@tanstack/react-query';
import type { JSX } from 'react';

import type { PersonKind } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { Card } from '@/portal/components/Card';
import { FormAlert } from '@/portal/features/auth/form';
import { useBecomeFriend } from '@/portal/features/profile/api';
import { refreshAfterPayment } from './refresh';
import './join.css';

export interface PayStepProps {
  /** The kind of account the step is for: a member pays dues, a friend may donate. */
  joiningAs: PersonKind;
  /** Called when the visitor changes their mind, with the kind they chose instead. */
  onJoiningAsChange: (kind: PersonKind) => void;
  /** Called when a payment settles, before `onDone`; skipping does not call it. */
  onPaid: () => void;
  /** Called to move on, after a payment or a friend's **Continue without a gift**. */
  onDone: () => void;
}

/** Step 4 of the join wizard: dues through `<Checkout/>`, or a friend's donation. */
export function PayStep({
  joiningAs,
  onJoiningAsChange: handleJoiningAsChange,
  onPaid: handlePaid,
  onDone: handleDone,
}: PayStepProps): JSX.Element {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const becomeFriend = useBecomeFriend();

  function handleSuccess(_result: CheckoutResult) {
    // Membership, payment history, and `profile_complete`/`membership` on the
    // user payload have all just moved.
    refreshAfterPayment(queryClient);
    handlePaid();
    handleDone();
  }

  /** Make the account a friend, unless the server holds it as one already, then `then`. */
  function asFriend(then: () => void): () => void {
    return () => {
      if (user?.kind === 'friend') {
        then();
        return;
      }
      becomeFriend.mutate({}, { onSuccess: then });
    };
  }

  // Each card is keyed by its kind, so switching starts the checkout afresh rather
  // than carrying the other kind's choices over.
  if (joiningAs === 'friend') {
    return (
      <Card key="friend" className="join-card" title="Donate to CalDART">
        <p className="muted join__intro">Friends pay no dues. A donation of any size helps.</p>
        <Checkout
          mode="contribute"
          onSuccess={(result) => asFriend(() => handleSuccess(result))()}
          onSkip={asFriend(handleDone)}
          onBecomeMember={() => handleJoiningAsChange('member')}
        />
        <FormAlert error={becomeFriend.error} />
      </Card>
    );
  }

  return (
    <Card key="member" className="join-card" title="Pay your dues">
      <p className="muted join__intro">
        Membership starts the moment the payment clears. You can add a contribution on top if you
        would like to support CalDART further.
      </p>
      <Checkout
        mode="join"
        onSuccess={handleSuccess}
        onBecomeFriend={() => handleJoiningAsChange('friend')}
      />
    </Card>
  );
}
