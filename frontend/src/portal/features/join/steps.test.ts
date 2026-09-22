import { describe, expect, it } from 'vitest';

import { makeUser } from '@test/handlers';
import type { MembershipStatus } from '../../api/types';
import {
  clampJoinStep,
  furthestJoinStep,
  isJoinStep,
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

describe('furthestJoinStep', () => {
  it('starts a visitor with no session at the account step', () => {
    expect(furthestJoinStep(null)).toBe('account');
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
  it('recognizes only the four real steps', () => {
    expect(isJoinStep('account')).toBe(true);
    expect(isJoinStep('done')).toBe(true);
    expect(isJoinStep('elsewhere')).toBe(false);
    expect(isJoinStep(undefined)).toBe(false);
  });

  it('orders the steps', () => {
    expect(joinStepIndex('account')).toBeLessThan(joinStepIndex('done'));
  });

  it('advances one step and stops at the end', () => {
    expect(nextJoinStep('account')).toBe('profile');
    expect(nextJoinStep('pay')).toBe('done');
    expect(nextJoinStep('done')).toBe('done');
  });

  it('takes the later of two steps', () => {
    expect(laterJoinStep('account', 'pay')).toBe('pay');
    expect(laterJoinStep('done', 'profile')).toBe('done');
  });
});
