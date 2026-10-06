/**
 * The portal's navigation, declared once with its role requirements.
 *
 * `roles: []` means "any signed-in user".  A user sees an entry when they hold
 * at least one of its roles; `system_admin` sees everything.
 */
import type { RoleSlug } from './api/types';

/** The rail's groups, in the order they render. */
export type NavGroup =
  'My account' | 'Operations' | 'Bulk email' | 'Finance' | 'Administration' | 'System';

export interface NavItem {
  /** Route path, relative to the `/portal` basename. */
  to: string;
  label: string;
  /** Any one of these roles grants the entry. Empty = any authenticated user. */
  roles: RoleSlug[];
  /**
   * Grouping shown as a small-caps heading in the rail, and as the eyebrow over
   * every page the entry leads to (`navEyebrow`).
   */
  group: NavGroup;
  /**
   * Match the route exactly rather than by prefix.
   *
   * The index route needs it, and so does any entry whose path is the prefix of
   * a deeper entry's: without it My profile marks itself current on My
   * aircraft, and Member check on Aircraft check, so the rail shows two current
   * pages at once.
   */
  end?: boolean;
  /**
   * Hide this entry from an effective friend: a friend by `kind` or by a
   * `friend_on` date that has arrived has no membership to renew.
   */
  hideForFriend?: boolean;
  /**
   * Hide this entry from a lifetime member, who has no term to renew and gives through
   * Donate like everyone else.
   */
  hideForLifetime?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', roles: [], group: 'My account', end: true },
  { to: '/profile', label: 'My profile', roles: [], group: 'My account', end: true },
  { to: '/profile/aircraft', label: 'My aircraft', roles: [], group: 'My account' },
  { to: '/payments', label: 'My payments', roles: [], group: 'My account' },
  { to: '/donate', label: 'Donate', roles: [], group: 'My account' },
  {
    to: '/renew',
    label: 'Renew',
    roles: [],
    group: 'My account',
    hideForFriend: true,
    hideForLifetime: true,
  },
  // `/change-password` is a real route with a real screen; without an entry
  // here nothing in the portal linked to it.
  { to: '/change-password', label: 'Change password', roles: [], group: 'My account' },
  { to: '/change-email', label: 'Change email', roles: [], group: 'My account' },
  { to: '/messages', label: 'Email to me', roles: [], group: 'My account' },
  { to: '/email-preferences', label: 'Email preferences', roles: [], group: 'My account' },

  // The two checks are where a person or an aircraft is verified, so the leader
  // API and `routes/leader.tsx` admit every verifying role, and the rail has to as
  // well or a verifier reaches these by URL only.
  {
    to: '/leader',
    label: 'Member check',
    roles: ['dart_leader', 'account_admin', 'user_admin', 'verifier'],
    group: 'Operations',
    end: true,
  },
  {
    to: '/leader/aircraft',
    label: 'Aircraft check',
    roles: ['dart_leader', 'account_admin', 'user_admin', 'verifier'],
    group: 'Operations',
  },

  // Bulk email has a group of its own. Compose opens a draft at
  // `/bulk-email/drafts/:id`, so Drafts and scheduled is current while one is written.
  // A DART leader sends to their own DART.
  {
    to: '/bulk-email/compose',
    label: 'Compose',
    roles: ['management', 'dart_leader'],
    group: 'Bulk email',
  },
  {
    to: '/bulk-email/drafts',
    label: 'Drafts and scheduled',
    roles: ['management', 'dart_leader'],
    group: 'Bulk email',
  },
  {
    to: '/bulk-email/sent',
    label: 'Sent',
    roles: ['management', 'dart_leader'],
    group: 'Bulk email',
  },
  {
    to: '/bulk-email/templates',
    label: 'Templates',
    roles: ['management'],
    group: 'Bulk email',
  },
  {
    to: '/bulk-email/groups',
    label: 'Recipient groups',
    roles: ['management'],
    group: 'Bulk email',
  },
  // A DART leader reads the answers to the callouts they sent and to their DART's.
  {
    to: '/bulk-email/callouts',
    label: 'Callouts',
    roles: ['management', 'dart_leader'],
    group: 'Bulk email',
  },
  { to: '/bulk-email/types', label: 'Email types', roles: ['system_admin'], group: 'Bulk email' },

  // Accounting admits a treasurer as well as an account administrator, and the rail
  // has to say so or a treasurer reaches it by URL only.
  {
    to: '/admin/payments',
    label: 'Accounting',
    roles: ['account_admin', 'treasurer'],
    group: 'Finance',
  },
  {
    to: '/admin/reminders',
    label: 'Reminders',
    roles: ['account_admin'],
    group: 'Finance',
  },

  // A DART leader reads the member list and its report too; the member record
  // behind each name stays the account administrator's.
  {
    to: '/admin/members',
    label: 'Members',
    roles: ['account_admin', 'dart_leader'],
    group: 'Administration',
  },
  {
    to: '/admin/aircraft',
    label: 'Aircraft',
    roles: ['account_admin'],
    group: 'Administration',
  },
  {
    to: '/admin/users',
    label: 'Roles and status',
    roles: ['user_admin'],
    group: 'Administration',
  },
  { to: '/admin/darts', label: 'DARTs', roles: ['account_admin'], group: 'Administration' },
  // The emailed reports are the finance roles', so a treasurer reaches the
  // screen too; the DART rosters on it are the account administrator's.
  {
    to: '/admin/reports',
    label: 'Emailed reports',
    roles: ['account_admin', 'treasurer'],
    group: 'Administration',
  },
  {
    to: '/admin/notifications',
    label: 'Notification emails',
    roles: ['account_admin'],
    group: 'Administration',
  },

  { to: '/system/health', label: 'Health and database', roles: ['system_admin'], group: 'System' },
  { to: '/system/emails', label: 'Sent emails', roles: ['system_admin'], group: 'System' },
  { to: '/system/scheduled', label: 'Scheduled tasks', roles: ['system_admin'], group: 'System' },
];

/** Order the rail renders groups in. */
export const NAV_GROUPS: NavGroup[] = [
  'My account',
  'Operations',
  'Bulk email',
  'Finance',
  'Administration',
  'System',
];

/**
 * Screens no rail entry leads to directly, and the group they belong to: the join
 * page a friend opens from the dashboard to become a member, and `/system`, which
 * opens the first System screen.
 */
const UNLISTED_AREAS: readonly { to: string; group: NavGroup }[] = [
  { to: '/membership', group: 'My account' },
  { to: '/system', group: 'System' },
];

/** True when `userRoles` satisfies `required` (`system_admin` satisfies all). */
export function hasAnyRole(userRoles: readonly RoleSlug[], required: readonly RoleSlug[]): boolean {
  if (userRoles.includes('system_admin')) return true;
  if (required.length === 0) return true;
  return required.some((role) => userRoles.includes(role));
}

/** What the rail knows about the reader beyond their roles. */
export interface NavReader {
  /**
   * A friend by kind or by an arrived `friend_on` date, or a member who has not paid
   * their first dues: somebody with no membership to renew.
   */
  isEffectiveFriend?: boolean;
  /** A lifetime member, who has no term to renew. */
  isLifetime?: boolean;
}

/**
 * The nav entries a user with `userRoles` may see, in declaration order.
 *
 * An effective friend loses an entry marked `hideForFriend`, and a lifetime member one
 * marked `hideForLifetime`: Renew is both.
 */
export function visibleNavItems(
  userRoles: readonly RoleSlug[],
  { isEffectiveFriend = false, isLifetime = false }: NavReader = {},
): NavItem[] {
  return NAV_ITEMS.filter(
    (item) =>
      hasAnyRole(userRoles, item.roles) &&
      !(item.hideForFriend === true && isEffectiveFriend) &&
      !(item.hideForLifetime === true && isLifetime),
  );
}

/** Visible entries bucketed by group, empty groups dropped. */
export function groupedNavItems(
  userRoles: readonly RoleSlug[],
  reader: NavReader = {},
): { group: NavGroup; items: NavItem[] }[] {
  const visible = visibleNavItems(userRoles, reader);
  return NAV_GROUPS.map((group) => ({
    group,
    items: visible.filter((item) => item.group === group),
  })).filter((bucket) => bucket.items.length > 0);
}

/** Whether `pathname` is the screen at `to` or one nested under it. */
function isWithin(to: string, pathname: string): boolean {
  if (to === '/') return pathname === '/';
  return pathname === to || pathname.startsWith(`${to}/`);
}

/**
 * The eyebrow over the page at `pathname`: the rail group of the entry that leads to
 * it.
 *
 * A page nested under an entry (a member record under Members) takes that entry's,
 * the deepest entry wins (Aircraft check over Member check), and a screen outside
 * the rail, such as sign-in or the join wizard, has none.  Every entry counts,
 * whatever the reader's roles, so the eyebrow never depends on who is reading.
 */
export function navEyebrow(pathname: string): string | null {
  const candidates = [
    ...NAV_ITEMS.map((item) => ({ to: item.to, eyebrow: item.group })),
    ...UNLISTED_AREAS.map((area) => ({ to: area.to, eyebrow: area.group })),
  ].filter((candidate) => isWithin(candidate.to, pathname));
  const deepest = candidates.reduce<{ to: string; eyebrow: string } | null>(
    (best, candidate) => (best === null || candidate.to.length > best.to.length ? candidate : best),
    null,
  );
  return deepest?.eyebrow ?? null;
}
