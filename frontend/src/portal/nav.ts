/**
 * The portal's navigation, declared once with its role requirements.
 *
 * `roles: []` means "any signed-in user".  A user sees an entry when they hold
 * at least one of its roles; `system_admin` sees everything.
 */
import type { RoleSlug } from './api/types';

export interface NavItem {
  /** Route path, relative to the `/portal` basename. */
  to: string;
  label: string;
  /** Any one of these roles grants the entry. Empty = any authenticated user. */
  roles: RoleSlug[];
  /** Grouping shown as a small-caps heading in the rail. */
  group: 'Membership' | 'Operations' | 'Administration' | 'System';
  /** Match the route exactly rather than by prefix (used for the index route). */
  end?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', roles: [], group: 'Membership', end: true },
  { to: '/profile', label: 'My profile', roles: [], group: 'Membership' },
  { to: '/profile/aircraft', label: 'My aircraft', roles: [], group: 'Membership' },
  { to: '/payments', label: 'Payments', roles: [], group: 'Membership' },
  { to: '/renew', label: 'Renew', roles: [], group: 'Membership' },
  // `/change-password` is a real route with a real screen; without an entry
  // here nothing in the portal linked to it.
  { to: '/change-password', label: 'Change password', roles: [], group: 'Membership' },

  // The leader API and `routes/leader.tsx` both admit `account_admin`, so the
  // rail has to as well or an account administrator reaches these by URL only.
  {
    to: '/leader',
    label: 'Member check',
    roles: ['dart_leader', 'account_admin'],
    group: 'Operations',
  },
  {
    to: '/leader/aircraft',
    label: 'Aircraft check',
    roles: ['dart_leader', 'account_admin'],
    group: 'Operations',
  },

  { to: '/admin/members', label: 'Members', roles: ['account_admin'], group: 'Administration' },
  { to: '/admin/aircraft', label: 'Aircraft', roles: ['account_admin'], group: 'Administration' },
  { to: '/admin/darts', label: 'DARTs', roles: ['account_admin'], group: 'Administration' },
  { to: '/admin/payments', label: 'Payments', roles: ['account_admin'], group: 'Administration' },
  {
    to: '/admin/reminders',
    label: 'Reminders',
    roles: ['account_admin'],
    group: 'Administration',
  },
  { to: '/admin/users', label: 'Users & roles', roles: ['user_admin'], group: 'Administration' },

  { to: '/system', label: 'System', roles: ['system_admin'], group: 'System' },
];

/** Order the rail renders groups in. */
export const NAV_GROUPS: NavItem['group'][] = [
  'Membership',
  'Operations',
  'Administration',
  'System',
];

/** True when `userRoles` satisfies `required` (`system_admin` satisfies all). */
export function hasAnyRole(userRoles: readonly RoleSlug[], required: readonly RoleSlug[]): boolean {
  if (userRoles.includes('system_admin')) return true;
  if (required.length === 0) return true;
  return required.some((role) => userRoles.includes(role));
}

/** The nav entries a user with `userRoles` may see, in declaration order. */
export function visibleNavItems(userRoles: readonly RoleSlug[]): NavItem[] {
  return NAV_ITEMS.filter((item) => hasAnyRole(userRoles, item.roles));
}

/** Visible entries bucketed by group, empty groups dropped. */
export function groupedNavItems(
  userRoles: readonly RoleSlug[],
): { group: NavItem['group']; items: NavItem[] }[] {
  const visible = visibleNavItems(userRoles);
  return NAV_GROUPS.map((group) => ({
    group,
    items: visible.filter((item) => item.group === group),
  })).filter((bucket) => bucket.items.length > 0);
}
