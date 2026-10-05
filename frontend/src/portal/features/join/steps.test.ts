import { afterEach, describe, expect, it } from 'vitest';

import { makeUser } from '@test/handlers';
import type { MembershipStatus } from '@/portal/api/types';
import {
  clampJoinStep,
  furthestJoinStep,
  holdFriendPayStep,
  isJoinStep,
  isOnboarded,
  joinStepIndex,
  joiningAs,
  laterJoinStep,
  nextJoinStep,
} from './steps';

const EXPIRED: MembershipStatus = {
  status: 'expired',
  expires_on: '2025-01-01',
  plan: 'Annual',
  is_lifetime: false,
};

/** What a friend reads as, however many terms they once held. */
const FRIEND: MembershipStatus = {
  status: 'friend',
  expires_on: null,
  plan: null,
  is_lifetime: false,
};

/** What somebody who chose to be a member and has not paid reads as. */
const NONE: MembershipStatus = { ...FRIEND, status: 'none' };

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

  it('sends a member-intent joiner who has not paid to the pay step', () => {
    expect(
      furthestJoinStep(makeUser({ kind: 'member', profile_complete: true, membership: NONE })),
    ).toBe('pay');
  });

  it('counts a member whose term ran out as joined, since renewing is not joining', () => {
    expect(furthestJoinStep(makeUser({ membership: EXPIRED }))).toBe('done');
  });

  it('sends a current member straight to done', () => {
    expect(furthestJoinStep(makeUser())).toBe('done');
  });

  it('resumes a friend with a complete profile on done when nothing holds the pay step', () => {
    expect(furthestJoinStep(makeUser({ kind: 'friend', membership: FRIEND }))).toBe('done');
  });

  it('still asks a friend with a thin profile for it first', () => {
    expect(
      furthestJoinStep(makeUser({ kind: 'friend', membership: FRIEND, profile_complete: false })),
    ).toBe('profile');
  });
});

const CURRENT: MembershipStatus = {
  status: 'current',
  expires_on: '2027-01-01',
  plan: 'Annual',
  is_lifetime: false,
};

describe('isOnboarded', () => {
  it('is false with nobody signed in', () => {
    expect(isOnboarded(null)).toBe(false);
  });

  it.each([
    // verified, complete, kind, membership, onboarded
    [true, true, 'member', CURRENT, true],
    [true, true, 'member', EXPIRED, true],
    [true, true, 'member', NONE, false],
    [true, true, 'friend', FRIEND, true],
    [true, false, 'member', CURRENT, false],
    [true, false, 'friend', FRIEND, false],
    [false, true, 'member', CURRENT, false],
    [false, true, 'friend', FRIEND, false],
    [false, false, 'member', NONE, false],
  ] as const)(
    'verified %s, profile complete %s, kind %s, membership %o reads %s',
    (emailVerified, profileComplete, kind, membership, expected) => {
      const user = makeUser({
        email_verified: emailVerified,
        profile_complete: profileComplete,
        kind,
        membership,
      });
      expect(isOnboarded(user)).toBe(expected);
    },
  );

  it('counts a member who asked to become a friend as joined, before the change is stored', () => {
    const user = makeUser({ kind: 'member', membership: FRIEND, friend_on: '2026-01-01' });
    expect(isOnboarded(user)).toBe(true);
  });

  it('counts a verified account an administrator created as joined, with no term or profile', () => {
    const user = makeUser({
      admin_created: true,
      email_verified: true,
      profile_complete: false,
      kind: 'member',
      membership: NONE,
    });
    expect(isOnboarded(user)).toBe(true);
  });

  it('holds an account an administrator created at the verify step until it is verified', () => {
    const user = makeUser({
      admin_created: true,
      email_verified: false,
      profile_complete: false,
      kind: 'member',
      membership: NONE,
    });
    expect(isOnboarded(user)).toBe(false);
  });

  it('resumes an unverified account an administrator created at the verify step', () => {
    const user = makeUser({ admin_created: true, email_verified: false, membership: NONE });
    expect(furthestJoinStep(user)).toBe('verify');
  });
});

describe('holdFriendPayStep', () => {
  afterEach(() => window.sessionStorage.clear());

  it('holds a friend at the pay step while this tab holds it for them', () => {
    const user = makeUser({ id: 7, kind: 'friend', membership: FRIEND });
    holdFriendPayStep(7);

    expect(isOnboarded(user)).toBe(false);
    expect(furthestJoinStep(user)).toBe('pay');
  });

  it('holds nobody else', () => {
    holdFriendPayStep(7);

    expect(isOnboarded(makeUser({ id: 8, kind: 'friend', membership: FRIEND }))).toBe(true);
  });

  it('lets the friend go once the hold is released', () => {
    const user = makeUser({ id: 7, kind: 'friend', membership: FRIEND });
    holdFriendPayStep(7);
    holdFriendPayStep(null);

    expect(isOnboarded(user)).toBe(true);
  });
});

describe('joiningAs', () => {
  it('walks a member-intent joiner through as a member, though they read as a friend', () => {
    expect(joiningAs(makeUser({ kind: 'member', membership: NONE }))).toBe('member');
  });

  it('walks a friend-intent joiner through as a friend', () => {
    expect(joiningAs(makeUser({ kind: 'friend', membership: FRIEND }))).toBe('friend');
  });

  it('walks nobody at all through as a member', () => {
    expect(joiningAs(null)).toBe('member');
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

  it('takes the later of two steps', () => {
    expect(laterJoinStep('account', 'pay')).toBe('pay');
    expect(laterJoinStep('done', 'profile')).toBe('done');
  });
});
