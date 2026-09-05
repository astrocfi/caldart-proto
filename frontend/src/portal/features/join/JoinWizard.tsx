/**
 * `/join` and `/join/:step` — the four-step join wizard (PLAN §8).
 *
 * The wizard is resumable: the step comes from the URL, but the *furthest*
 * step the visitor may be on is derived from the server's view of them
 * (session, `profile_complete`, membership), so closing the tab half way
 * through and coming back lands you where you left off.  Going back is always
 * allowed; skipping ahead is not.
 */
import { useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';

import { useAuth } from '../../auth/useAuth';
import { Page } from '../../components/Page';
import { AccountStep } from './AccountStep';
import { DoneStep } from './DoneStep';
import { PayStep } from './PayStep';
import { ProfileStep } from './ProfileStep';
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
  const navigate = useNavigate();
  const { user, isLoading } = useAuth();
  // Steps finished in this tab, so a step does not bounce backwards while
  // `/auth/me` is still being refetched behind the scenes.
  const [reached, setReached] = useState<JoinStep>('account');

  if (isLoading) {
    return (
      <Page title="Join CalDART" eyebrow="Membership">
        <p className="muted" role="status">
          Loading…
        </p>
      </Page>
    );
  }

  const furthest = laterJoinStep(furthestJoinStep(user), reached);

  if (!isJoinStep(stepParam)) {
    return <Navigate to={`/join/${furthest}`} replace />;
  }

  const current = clampJoinStep(stepParam, furthest);
  if (current !== stepParam) {
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
      {current === 'done' ? <DoneStep /> : null}
    </Page>
  );
}
