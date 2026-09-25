/**
 * The user guide the site serves at `/docs/`, and which of its pages a user
 * should land on.
 *
 * The guide is Sphinx output served by Django, not a portal route, so a link
 * to it is a full-page navigation out of the SPA.
 */
import type { RoleSlug } from './api/types';

/** Where Django serves the built user guide. */
export const GUIDE_PREFIX = '/docs/';

/**
 * Each role's own page, in the order that decides between a user's roles:
 * the most specific role a user holds picks the page, and a member with
 * nothing else lands on the member guide. Every page links to the rest.
 */
const GUIDE_PAGES: readonly [RoleSlug, string][] = [
  ['system_admin', 'system-administrator-guide'],
  ['website_admin', 'website-administrator-guide'],
  ['account_admin', 'account-administrator-guide'],
  ['treasurer', 'payments'],
  ['user_admin', 'user-administrator'],
  ['dart_leader', 'dart-leader-guide'],
  ['member', 'member-guide'],
];

/** The guide page for a user holding `roles`; the guide's front page for none. */
export function guidePath(roles: readonly RoleSlug[]): string {
  const match = GUIDE_PAGES.find(([role]) => roles.includes(role));
  return match ? `${GUIDE_PREFIX}${match[1]}/` : GUIDE_PREFIX;
}

/** True when `path` is a page of the guide rather than a portal route. */
export function isGuidePath(path: string): boolean {
  return path === GUIDE_PREFIX.slice(0, -1) || path.startsWith(GUIDE_PREFIX);
}

/** Leave the SPA for a guide page: the browser loads it from Django. */
export function openGuide(path: string): void {
  window.location.assign(path);
}
