import { describe, expect, it } from 'vitest';

import { guidePath, isGuidePath } from './guide';

describe('guidePath', () => {
  it('sends a plain member to the member guide', () => {
    expect(guidePath(['member'])).toBe('/docs/member-guide/');
  });

  it('sends each administrator to their own guide', () => {
    expect(guidePath(['member', 'dart_leader'])).toBe('/docs/dart-leader-guide/');
    expect(guidePath(['member', 'user_admin'])).toBe('/docs/user-administrator/');
    expect(guidePath(['member', 'treasurer'])).toBe('/docs/payments/');
    expect(guidePath(['member', 'account_admin'])).toBe('/docs/account-administrator-guide/');
    expect(guidePath(['member', 'website_admin'])).toBe('/docs/website-administrator-guide/');
    expect(guidePath(['member', 'system_admin'])).toBe('/docs/system-administrator-guide/');
  });

  it('prefers the more specific of two roles whichever order they come in', () => {
    expect(guidePath(['dart_leader', 'account_admin'])).toBe('/docs/account-administrator-guide/');
    expect(guidePath(['account_admin', 'dart_leader'])).toBe('/docs/account-administrator-guide/');
  });

  it('falls back to the front page for a user with no role', () => {
    expect(guidePath([])).toBe('/docs/');
  });
});

describe('isGuidePath', () => {
  it('recognizes the guide root and its pages', () => {
    expect(isGuidePath('/docs')).toBe(true);
    expect(isGuidePath('/docs/')).toBe(true);
    expect(isGuidePath('/docs/member-guide/')).toBe(true);
  });

  it('leaves portal routes alone', () => {
    expect(isGuidePath('/profile')).toBe(false);
    expect(isGuidePath('/documents/')).toBe(false);
    expect(isGuidePath('/')).toBe(false);
  });
});
