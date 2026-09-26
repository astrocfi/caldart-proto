import { describe, expect, it } from 'vitest';

import { makeUser } from '@test/handlers';
import type { MembershipStatus } from '@/portal/api/types';
import {
  clampJoinStep,
  furthestJoinStep,
  isJoinStep,
  joinStepEyebrow,
  joinStepIndex,
  laterJoinStep,
  nextJoinStep,
} from './steps';

const EXPIRED: MembershipStatus = {
  status: 'expired',
  expires_on: '2025-01-01',
  plan: 'Annual',
  is_lifetime: false,
};

const NONE: MembershipStatus = {
  status: 'none',
  expires_on: null,
  plan: null,
  is_lifetime: false,
};

const FRIEND: MembershipStatus = { ...NONE, status: 'friend' };

describe('furthestJoinStep', () => {
  it('starts a visitor with no session at the account step', () => {
    expect(furthestJoinStep(null)).toBe('account');
  });

  it('holds a signed-in user with an unverified address at the verify step', () => {
    expect(furthestJoinStep(makeUser({ email_verified: false, profile_complete: false }))).toBe(
      'verify',
    );
  });

  it('holds an unverified address at the verify step even with a complete profile', () => {
    expect(furthestJoinStep(makeUser({ email_verified: false, membership: NONE }))).toBe('verify');
  });

  it('sends a signed-in member with a thin profile to the profile step', () => {
    expect(furthestJoinStep(makeUser({ profile_complete: false }))).toBe('profile');
  });

  it('sends a complete profile without a membership to the pay step', () => {
    expect(furthestJoinStep(makeUser({ profile_complete: true, membership: NONE }))).toBe('pay');
  });

  it('treats an expired membership as still owing the fee', () => {
    expect(furthestJoinStep(makeUser({ membership: EXPIRED }))).toBe('pay');
  });

  it('sends a current member straight to done', () => {
    expect(furthestJoinStep(makeUser())).toBe('done');
  });

  it('never holds a friend with a complete profile at the pay step', () => {
    expect(furthestJoinStep(makeUser({ kind: 'friend', membership: FRIEND }))).toBe('done');
  });

  it('still asks a friend with a thin profile for it first', () => {
    expect(
      furthestJoinStep(makeUser({ kind: 'friend', membership: FRIEND, profile_complete: false })),
    ).toBe('profile');
  });
});

describe('clampJoinStep', () => {
  it('lets a visitor go back to an earlier step', () => {
    expect(clampJoinStep('profile', 'done')).toBe('profile');
  });

  it('refuses to let them skip ahead', () => {
    expect(clampJoinStep('pay', 'account')).toBe('account');
    expect(clampJoinStep('done', 'profile')).toBe('profile');
  });

  it('leaves the current step alone', () => {
    expect(clampJoinStep('pay', 'pay')).toBe('pay');
  });
});

describe('step helpers', () => {
  it('recognizes only the five real steps', () => {
    expect(isJoinStep('account')).toBe(true);
    expect(isJoinStep('verify')).toBe(true);
    expect(isJoinStep('done')).toBe(true);
    expect(isJoinStep('elsewhere')).toBe(false);
    expect(isJoinStep(undefined)).toBe(false);
  });

  it('orders the steps', () => {
    expect(joinStepIndex('account')).toBeLessThan(joinStepIndex('done'));
  });

  it('advances one step and stops at the end', () => {
    expect(nextJoinStep('account')).toBe('verify');
    expect(nextJoinStep('verify')).toBe('profile');
    expect(nextJoinStep('pay')).toBe('done');
    expect(nextJoinStep('done')).toBe('done');
  });

  it('orders verify between account and profile', () => {
    expect(joinStepIndex('verify')).toBe(1);
  });

  it('numbers a step out of all five', () => {
    expect(joinStepEyebrow('profile')).toBe('Step 3 of 5');
  });

  it('names the kind being joined as when it is given', () => {
    expect(joinStepEyebrow('verify', 'friend')).toBe('Step 2 of 5 · Joining as a friend');
    expect(joinStepEyebrow('verify', 'member')).toBe('Step 2 of 5 · Joining as a member');
  });

  it('takes the later of two steps', () => {
    expect(laterJoinStep('account', 'pay')).toBe('pay');
    expect(laterJoinStep('done', 'profile')).toBe('done');
  });
});
