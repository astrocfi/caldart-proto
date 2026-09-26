/**
 * The join wizard's five steps and the rules for resuming one.
 *
 * Pure functions so the resume logic can be tested on its own: given the
 * signed-in user (or nobody), which step should the visitor be on, and may
 * they be on the step the URL asks for?
 */
import type { User } from '@/portal/api/types';

export const JOIN_STEPS = ['account', 'verify', 'profile', 'pay', 'done'] as const;

export type JoinStep = (typeof JOIN_STEPS)[number];

export const JOIN_STEP_LABELS: Record<JoinStep, string> = {
  account: 'Account',
  verify: 'Verify',
  profile: 'Profile',
  pay: 'Pay',
  done: 'Done',
};

/** True when `value` is one of the join wizard's step names. */
export function isJoinStep(value: string | undefined): value is JoinStep {
  return value !== undefined && (JOIN_STEPS as readonly string[]).includes(value);
}

/** The zero-based position of `step` in the wizard's order. */
export function joinStepIndex(step: JoinStep): number {
  return JOIN_STEPS.indexOf(step);
}

/** The eyebrow over a step's card, e.g. `Step 3 of 5`. */
export function joinStepEyebrow(step: JoinStep): string {
  return `Step ${joinStepIndex(step) + 1} of ${JOIN_STEPS.length}`;
}

/** The step after `step`, or `step` itself when it is the last one. */
export function nextJoinStep(step: JoinStep): JoinStep {
  return JOIN_STEPS[Math.min(joinStepIndex(step) + 1, JOIN_STEPS.length - 1)] ?? step;
}

/**
 * How far the visitor has got, from the server's view of them.
 *
 * No session at all means they still need an account; an address nobody has
 * verified yet means they still have to click the link we mailed; a session
 * without a usable profile means the profile step; a complete profile without a
 * current membership means they still owe us the fee; anything else means they
 * have joined.
 */
export function furthestJoinStep(user: User | null): JoinStep {
  if (!user) return 'account';
  if (!user.email_verified) return 'verify';
  if (!user.profile_complete) return 'profile';
  if (user.membership.status !== 'current') return 'pay';
  return 'done';
}

/** Later of two steps — used to hold ground while `/auth/me` catches up. */
export function laterJoinStep(a: JoinStep, b: JoinStep): JoinStep {
  return joinStepIndex(a) >= joinStepIndex(b) ? a : b;
}

/**
 * Where the visitor may actually go.
 *
 * Going *back* is always allowed — someone may want to fix their profile
 * before paying — but they cannot skip ahead of what they have finished.
 */
export function clampJoinStep(requested: JoinStep, furthest: JoinStep): JoinStep {
  return joinStepIndex(requested) > joinStepIndex(furthest) ? furthest : requested;
}
