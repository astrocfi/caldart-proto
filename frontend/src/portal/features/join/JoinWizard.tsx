/**
 * `/join` and `/join/:step` — the five-step join wizard.
 *
 * The wizard is resumable: the step comes from the URL, but the *furthest*
 * step the visitor may be on is derived from the server's view of them
 * (session, `email_verified`, `profile_complete`, membership), so closing the
 * tab half way through and coming back lands you where you left off.  Going
 * back is always allowed; skipping ahead is not.  The verify step has nothing to
 * offer an address that is already verified, so the wizard passes over it.
 *
 * The one exception is a visitor coming back from a redirect-based payment
 * method: Stripe returns them to `/join/done?payment_id=…`, and at that
 * moment the server still says they owe us the fee.  Clamping would send them
 * to `/join/pay` and throw the payment reference away, so the wizard holds the
 * `done` step and lets `<ReturnStep/>` settle the payment first.
 *
 * A friend walks the same five steps, but owes no dues: their pay step offers a
 * contribution they may skip, and a friend with a complete profile resumes on the
 * done step rather than being held at paying.
 */
import { useCallback, useState } from 'react';
import type { JSX } from 'react';
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';

import { useAuth } from '@/portal/auth/useAuth';
import { Page } from '@/portal/components/Page';
import { AccountStep } from './AccountStep';
import { DoneStep } from './DoneStep';
import { PayStep } from './PayStep';
import { ProfileStep } from './ProfileStep';
import { refreshAfterPayment } from './refresh';
import { ReturnStep } from './ReturnStep';
import { StepIndicator } from './StepIndicator';
import {
  clampJoinStep,
  furthestJoinStep,
  isJoinStep,
  joiningAs,
  laterJoinStep,
  nextJoinStep,
} from './steps';
import type { JoinStep } from './steps';
import { VerifyStep } from './VerifyStep';
import './join.css';

const LEDE: Record<JoinStep, string> = {
  account: 'Membership is $45 a year, or $650 for life. It takes about three minutes.',
  verify: 'We need to know the address is yours before you go on.',
  profile: 'Tell us how to reach you and what you fly.',
  pay: 'Card, Apple Pay, Google Pay, or PayPal. Your membership starts immediately.',
  done: 'You are a member of the California DART Network.',
};

/** Where a friend's walk through the wizard reads differently from a member's. */
const FRIEND_LEDE: Partial<Record<JoinStep, string>> = {
  pay: 'Card, Apple Pay, Google Pay, or PayPal. Any amount helps, and none is required.',
  done: 'You are a friend of the California DART Network.',
};

/** Renders the join wizard step named by the URL, redirecting to a valid one. */
export function JoinWizard(): JSX.Element {
  const { step: stepParam } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user, isLoading } = useAuth();
  // Steps finished in this tab, so a step does not bounce backwards while
  // `/auth/me` is still being refetched behind the scenes.
  const [reached, setReached] = useState<JoinStep>('account');
  // Set once a redirect return has been confirmed, so the wizard stops holding
  // the `done` step open on the payment's behalf.
  const [returnSettled, setReturnSettled] = useState(false);

  const handleReturnSettled = useCallback(() => {
    refreshAfterPayment(queryClient);
    setReached('done');
    setReturnSettled(true);
    // The provider's query string has done its job; drop it so a refresh does
    // not confirm the same payment twice.
    void navigate('/join/done', { replace: true });
  }, [navigate, queryClient]);

  if (isLoading) {
    return (
      <div className="join-shell">
        <Page title="Join CalDART" eyebrow="Membership">
          <p className="muted" role="status">
            Loading…
          </p>
        </Page>
      </div>
    );
  }

  // A signed-in visitor whose URL still carries the provider's payment
  // reference has a payment to finish before the wizard may judge them.
  const returning = Boolean(
    user && stepParam === 'done' && searchParams.has('payment_id') && !returnSettled,
  );

  const furthest = laterJoinStep(furthestJoinStep(user), reached);

  if (!isJoinStep(stepParam)) {
    return <Navigate to={`/join/${furthest}`} replace />;
  }

  const clamped = returning ? 'done' : clampJoinStep(stepParam, furthest);
  const current = clamped === 'verify' && user?.email_verified === true ? 'profile' : clamped;
  if (!returning && current !== stepParam) {
    return <Navigate to={`/join/${current}`} replace />;
  }

  const lede = (joiningAs(user) === 'friend' ? FRIEND_LEDE[current] : undefined) ?? LEDE[current];

  function advance(from: JoinStep) {
    const next = nextJoinStep(from);
    setReached((seen) => laterJoinStep(seen, next));
    void navigate(`/join/${next}`);
  }

  return (
    <div className="join-shell">
      <Page title="Join CalDART" eyebrow="Membership" lede={lede}>
        <StepIndicator current={current} />
        {current === 'account' ? <AccountStep onDone={() => advance('account')} /> : null}
        {current === 'verify' ? <VerifyStep onDone={() => advance('verify')} /> : null}
        {current === 'profile' ? <ProfileStep onDone={() => advance('profile')} /> : null}
        {current === 'pay' ? <PayStep onDone={() => advance('pay')} /> : null}
        {current === 'done' ? (
          returning ? (
            <ReturnStep onSettled={handleReturnSettled} />
          ) : (
            <DoneStep />
          )
        ) : null}
      </Page>
    </div>
  );
}
