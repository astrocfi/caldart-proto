/**
 * `/join` and `/join/:step` — the four-step join wizard (PLAN §8).
 *
 * The wizard is resumable: the step comes from the URL, but the *furthest*
 * step the visitor may be on is derived from the server's view of them
 * (session, `profile_complete`, membership), so closing the tab half way
 * through and coming back lands you where you left off.  Going back is always
 * allowed; skipping ahead is not.
 *
 * The one exception is a visitor coming back from a redirect-based payment
 * method: Stripe returns them to `/join/done?payment_id=…`, and at that
 * moment the server still says they owe us the fee.  Clamping would send them
 * to `/join/pay` and throw the payment reference away, so the wizard holds the
 * `done` step and lets `<ReturnStep/>` settle the payment first (PLAN §10).
 */
import { useCallback, useState } from 'react';
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';

import { useAuth } from '../../auth/useAuth';
import { Page } from '../../components/Page';
import { AccountStep } from './AccountStep';
import { DoneStep } from './DoneStep';
import { PayStep } from './PayStep';
import { ProfileStep } from './ProfileStep';
import { refreshAfterPayment } from './refresh';
import { ReturnStep } from './ReturnStep';
import { StepIndicator } from './StepIndicator';
import { clampJoinStep, furthestJoinStep, isJoinStep, laterJoinStep, nextJoinStep } from './steps';
import type { JoinStep } from './steps';
import './join.css';

const LEDE: Record<JoinStep, string> = {
  account: 'Membership is $45 a year, or $650 for life. It takes about three minutes.',
  profile: 'Tell us how to reach you and what you fly.',
  pay: 'Card, Apple Pay, Google Pay or PayPal. Your membership starts immediately.',
  done: 'You are a member of the California DART Network.',
};

export function JoinWizard() {
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
    navigate('/join/done', { replace: true });
  }, [navigate, queryClient]);

  if (isLoading) {
    return (
      <Page title="Join CalDART" eyebrow="Membership">
        <p className="muted" role="status">
          Loading…
        </p>
      </Page>
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

  const current = returning ? 'done' : clampJoinStep(stepParam, furthest);
  if (!returning && current !== stepParam) {
    return <Navigate to={`/join/${current}`} replace />;
  }

  function advance(from: JoinStep) {
    const next = nextJoinStep(from);
    setReached((seen) => laterJoinStep(seen, next));
    navigate(`/join/${next}`);
  }

  return (
    <Page title="Join CalDART" eyebrow="Membership" lede={LEDE[current]}>
      <StepIndicator current={current} />
      {current === 'account' ? <AccountStep onDone={() => advance('account')} /> : null}
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
  );
}
