/**
 * Where the Help button on each portal screen sends the visitor: the page of
 * the user guide that documents the screen they are looking at.
 */
import { matchPath } from 'react-router-dom';

import { GUIDE_PREFIX } from './guide';

export interface HelpPage {
  /** A React Router path pattern, matched against the current location's pathname. */
  readonly pattern: string;
  /**
   * The user guide page, a path under `docs/user/` without the `.rst` extension
   * (`member/profile` is `docs/user/member/profile.rst`).
   */
  readonly slug: string;
}

/**
 * Every portal route, mapped to its page of the user guide.
 *
 * Order matters wherever a wildcard segment could also match a more specific
 * path: `/admin/payments/:id` is listed after `list`, `donors`, and the rest
 * of that group's named paths, so those win the match instead of falling
 * into the `:id` wildcard.
 */
export const HELP_PAGES: readonly HelpPage[] = [
  { pattern: '/', slug: 'member/dashboard' },
  { pattern: '/profile', slug: 'member/profile' },
  { pattern: '/profile/aircraft', slug: 'member/my-aircraft' },
  { pattern: '/payments', slug: 'member/payments' },
  { pattern: '/donate', slug: 'member/donate' },
  { pattern: '/renew', slug: 'member/renew' },
  { pattern: '/membership/join', slug: 'member/become-a-member' },
  { pattern: '/change-email', slug: 'member/change-email' },
  { pattern: '/change-password', slug: 'member/change-password' },
  { pattern: '/login', slug: 'member/sign-in' },
  { pattern: '/forgot-password', slug: 'member/forgot-password' },
  { pattern: '/reset-password', slug: 'member/reset-password' },
  { pattern: '/verify-email', slug: 'member/verify-email' },
  { pattern: '/join', slug: 'member/join' },
  { pattern: '/join/:step', slug: 'member/join' },
  { pattern: '/leader', slug: 'admin/member-check' },
  { pattern: '/leader/aircraft', slug: 'admin/aircraft-check' },
  { pattern: '/admin/members', slug: 'admin/members' },
  { pattern: '/admin/members/new', slug: 'admin/new-member' },
  { pattern: '/admin/members/:id', slug: 'admin/member-record' },
  { pattern: '/admin/aircraft', slug: 'admin/aircraft-register' },
  { pattern: '/admin/aircraft/:id', slug: 'admin/aircraft-record' },
  { pattern: '/admin/darts', slug: 'admin/darts' },
  { pattern: '/admin/payments', slug: 'finance/overview' },
  { pattern: '/admin/payments/list', slug: 'finance/payment-list' },
  { pattern: '/admin/payments/renewals', slug: 'finance/renewals' },
  { pattern: '/admin/payments/reconciliation', slug: 'finance/reconciliation' },
  { pattern: '/admin/payments/contributions', slug: 'finance/contributions' },
  { pattern: '/admin/payments/record', slug: 'finance/record-payment' },
  { pattern: '/admin/payments/members/:userId', slug: 'finance/member-ledger' },
  { pattern: '/admin/payments/donors', slug: 'finance/donors' },
  { pattern: '/admin/payments/:id', slug: 'finance/payment-record' },
  { pattern: '/admin/reminders', slug: 'admin/reminders' },
  { pattern: '/admin/reports', slug: 'admin/reports' },
  { pattern: '/admin/users', slug: 'admin/users' },
  { pattern: '/admin/users/:id', slug: 'admin/user-record' },
  { pattern: '/system', slug: 'admin/system' },
];

/** The user guide page for the screen at `pathname`, or the guide's front page for none. */
export function helpPath(pathname: string): string {
  const page = HELP_PAGES.find(({ pattern }) => matchPath(pattern, pathname) !== null);
  return page ? `${GUIDE_PREFIX}${page.slug}/` : GUIDE_PREFIX;
}
