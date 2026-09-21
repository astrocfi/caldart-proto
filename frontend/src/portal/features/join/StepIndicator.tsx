/** The wizard's progress rail: numbered, ticked once passed, wraps on a phone. */
import type { JSX } from 'react';

import { JOIN_STEPS, JOIN_STEP_LABELS, joinStepIndex } from './steps';
import type { JoinStep } from './steps';
import './join.css';

export interface StepIndicatorProps {
  current: JoinStep;
}

/** Renders the join wizard's numbered progress rail, ticking off finished steps. */
export function StepIndicator({ current }: StepIndicatorProps): JSX.Element {
  const currentIndex = joinStepIndex(current);

  return (
    <ol className="join-steps" aria-label="Join progress">
      {JOIN_STEPS.map((step, index) => {
        const state = index < currentIndex ? 'done' : index === currentIndex ? 'current' : 'todo';
        return (
          <li
            key={step}
            className="join-steps__step"
            data-state={state}
            aria-current={state === 'current' ? 'step' : undefined}
          >
            <span>{JOIN_STEP_LABELS[step]}</span>
            {state === 'done' ? <span className="visually-hidden">completed</span> : null}
          </li>
        );
      })}
    </ol>
  );
}
