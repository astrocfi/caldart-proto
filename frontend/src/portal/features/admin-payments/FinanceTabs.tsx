/**
 * The finance area's tab bar, shown at the top of every screen in it.
 *
 * The area is one job — the money — split across screens that ask different
 * questions of it, so the bar stays put while the screen beneath it changes.
 * A screen that hangs off a tab rather than being one — a payment detail, a
 * member ledger — names the tab it came from with `current`, so the reader can
 * still see where in the area they are standing.
 */
import type { JSX } from 'react';
import { Link, useLocation } from 'react-router-dom';

import type { RoleSlug } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { hasAnyRole } from '@/portal/nav';

export interface FinanceTab {
  to: string;
  label: string;
  /** Match the path exactly rather than by prefix. */
  end?: boolean;
  /** Roles that may see the tab; every finance role when left out. */
  roles?: RoleSlug[];
}

/** The finance area's screens, in the order the bar shows them. */
export const FINANCE_TABS: FinanceTab[] = [
  { to: '/admin/payments', label: 'Overview', end: true },
  { to: '/admin/payments/list', label: 'Payments' },
  { to: '/admin/payments/renewals', label: 'Renewals' },
  { to: '/admin/payments/reconciliation', label: 'Reconciliation' },
  { to: '/admin/payments/contributions', label: 'Contributions' },
  // The treasurer's own: an account administrator does not track donors.
  { to: '/admin/payments/donors', label: 'Donors', roles: ['treasurer'] },
];

/** Whether `path` is the tab's own screen, or one nested under it. */
export function isTabCurrent(tab: FinanceTab, path: string): boolean {
  if (tab.end === true) return path === tab.to;
  return path === tab.to || path.startsWith(`${tab.to}/`);
}

export interface FinanceTabsProps {
  /** The path to mark as current, when it is not the one in the address bar. */
  current?: string;
}

/** The finance area's tab bar, with the current screen's tab marked. */
export function FinanceTabs({ current }: FinanceTabsProps): JSX.Element {
  const location = useLocation();
  const path = current ?? location.pathname;
  const { roles } = useAuth();
  const tabs = FINANCE_TABS.filter((tab) => hasAnyRole(roles, tab.roles ?? []));

  return (
    <nav className="finance-tabs" aria-label="Finance sections">
      {tabs.map((tab) => (
        <Link
          key={tab.to}
          to={tab.to}
          className="finance-tabs__tab"
          aria-current={isTabCurrent(tab, path) ? 'page' : undefined}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}
