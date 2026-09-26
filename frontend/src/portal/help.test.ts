import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import type { RouteObject } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { HELP_PAGES, helpPath } from './help';
import { routes } from './routes';

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

/** The user guide's source directory, `docs/user/` at the repository root. */
const USER_GUIDE_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../../docs/user');

/**
 * Every screen path in the route table, as a pattern rooted at `/`.
 *
 * A route with a `path` or `index: true` is a screen; a pathless route (a role guard or
 * the session guard) only groups its children, and the `*` catch-all is the not-found
 * page, which has no Help page of its own.
 */
function screenPatterns(tree: readonly RouteObject[], parent = ''): string[] {
  return tree.flatMap((route) => {
    const own = route.path === undefined ? parent : join(parent === '' ? '/' : parent, route.path);
    const children = screenPatterns(route.children ?? [], own);
    const isScreen = (route.index === true || route.path !== undefined) && route.path !== '*';
    return isScreen && route.children === undefined ? [own, ...children] : children;
  });
}

/** `pattern` with each `:param` segment replaced by a concrete value. */
function concretePath(pattern: string): string {
  return pattern.replace(/:[A-Za-z]+/g, '42');
}

const SCREEN_PATTERNS = screenPatterns(routes);

describe('the Help pages and the route table', () => {
  it('finds the screens in the route table', () => {
    expect(SCREEN_PATTERNS).toContain('/admin/payments/:id');
  });

  it.each(SCREEN_PATTERNS)('gives the route %s a Help page', (pattern) => {
    expect(HELP_PAGES.map((page) => page.pattern)).toContain(pattern);
  });

  it.each(SCREEN_PATTERNS)('sends a visitor at %s to the page mapped to that route', (pattern) => {
    const page = HELP_PAGES.find((candidate) => candidate.pattern === pattern);
    expect(helpPath(concretePath(pattern))).toBe(`/docs/${page?.slug ?? '(none)'}/`);
  });

  it.each(HELP_PAGES.map((page) => page.pattern))(
    'maps the Help pattern %s to a route that exists',
    (pattern) => {
      expect(SCREEN_PATTERNS).toContain(pattern);
    },
  );

  it.each(HELP_PAGES.map((page) => page.slug))('finds docs/user/%s.rst', (slug) => {
    expect(existsSync(join(USER_GUIDE_DIR, `${slug}.rst`))).toBe(true);
  });
});
