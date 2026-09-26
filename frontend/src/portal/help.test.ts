import { describe, expect, it } from 'vitest';

import { HELP_PAGES, helpPath } from './help';

/**
 * Every route pattern the Help button must recognize, transcribed by hand rather than
 * read from `HELP_PAGES`, so a pattern the table drops still fails this test.
 */
const HELP_ROUTE_PATTERNS: readonly string[] = [
  '/',
  '/profile',
  '/profile/aircraft',
  '/payments',
  '/donate',
  '/renew',
  '/membership/join',
  '/change-email',
  '/change-password',
  '/login',
  '/forgot-password',
  '/reset-password',
  '/verify-email',
  '/join',
  '/join/:step',
  '/leader',
  '/leader/aircraft',
  '/admin/members',
  '/admin/members/new',
  '/admin/members/:id',
  '/admin/aircraft',
  '/admin/aircraft/:id',
  '/admin/darts',
  '/admin/payments',
  '/admin/payments/list',
  '/admin/payments/renewals',
  '/admin/payments/reconciliation',
  '/admin/payments/contributions',
  '/admin/payments/record',
  '/admin/payments/members/:userId',
  '/admin/payments/donors',
  '/admin/payments/:id',
  '/admin/reminders',
  '/admin/reports',
  '/admin/users',
  '/admin/users/:id',
  '/system',
];

/**
 * A concrete pathname for each pattern above, paired with the exact guide page it must
 * open. Every value is transcribed by hand rather than read from `HELP_PAGES`, so a wrong
 * slug or a swapped mapping fails a specific case instead of passing against itself.
 */
const HELP_PAGE_CASES: readonly [pathname: string, expectedHref: string][] = [
  ['/', '/docs/member/dashboard/'],
  ['/profile', '/docs/member/profile/'],
  ['/profile/aircraft', '/docs/member/my-aircraft/'],
  ['/payments', '/docs/member/payments/'],
  ['/donate', '/docs/member/donate/'],
  ['/renew', '/docs/member/renew/'],
  ['/membership/join', '/docs/member/become-a-member/'],
  ['/change-email', '/docs/member/change-email/'],
  ['/change-password', '/docs/member/change-password/'],
  ['/login', '/docs/member/sign-in/'],
  ['/forgot-password', '/docs/member/forgot-password/'],
  ['/reset-password', '/docs/member/reset-password/'],
  ['/verify-email', '/docs/member/verify-email/'],
  ['/join', '/docs/member/join/'],
  ['/join/2', '/docs/member/join/'],
  ['/leader', '/docs/admin/member-check/'],
  ['/leader/aircraft', '/docs/admin/aircraft-check/'],
  ['/admin/members', '/docs/admin/members/'],
  ['/admin/members/new', '/docs/admin/new-member/'],
  ['/admin/members/42', '/docs/admin/member-record/'],
  ['/admin/aircraft', '/docs/admin/aircraft-register/'],
  ['/admin/aircraft/42', '/docs/admin/aircraft-record/'],
  ['/admin/darts', '/docs/admin/darts/'],
  ['/admin/payments', '/docs/finance/overview/'],
  ['/admin/payments/list', '/docs/finance/payment-list/'],
  ['/admin/payments/renewals', '/docs/finance/renewals/'],
  ['/admin/payments/reconciliation', '/docs/finance/reconciliation/'],
  ['/admin/payments/contributions', '/docs/finance/contributions/'],
  ['/admin/payments/record', '/docs/finance/record-payment/'],
  ['/admin/payments/members/9', '/docs/finance/member-ledger/'],
  ['/admin/payments/donors', '/docs/finance/donors/'],
  ['/admin/payments/42', '/docs/finance/payment-record/'],
  ['/admin/reminders', '/docs/admin/reminders/'],
  ['/admin/reports', '/docs/admin/reports/'],
  ['/admin/users', '/docs/admin/users/'],
  ['/admin/users/42', '/docs/admin/user-record/'],
  ['/system', '/docs/admin/system/'],
];

describe('helpPath', () => {
  it('matches every route pattern the Help button must recognize, in match order', () => {
    expect(HELP_PAGES.map((page) => page.pattern)).toEqual(HELP_ROUTE_PATTERNS);
  });

  it.each(HELP_PAGE_CASES)('sends %s to %s', (pathname, expectedHref) => {
    expect(helpPath(pathname)).toBe(expectedHref);
  });

  it('falls back to the guide front page for a route with no Help page', () => {
    expect(helpPath('/not-a-real-screen')).toBe('/docs/');
  });

  it('falls into the /admin/payments/:id wildcard for an id that names none of the above', () => {
    expect(helpPath('/admin/payments/7')).toBe('/docs/finance/payment-record/');
  });

  it('does not let /admin/members/:id swallow /admin/members/new', () => {
    expect(helpPath('/admin/members/new')).toBe('/docs/admin/new-member/');
  });
});
