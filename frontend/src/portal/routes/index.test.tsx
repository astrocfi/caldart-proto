/**
 * The portal's real route table, path by path, identity by identity.
 *
 * The subject here is the table and its guards, so every page module is
 * replaced by a stub that renders its name; the layout, the guards and the
 * not-found page are the real ones.  The expected outcomes are written out
 * below rather than derived from `hasAnyRole`, so a guard that loses a role
 * fails a case instead of agreeing with itself.
 */
import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { makeUser, signedInAs } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import type { RoleSlug } from '../api/types';
import { routes } from './index';

const { pageStub } = vi.hoisted(() => ({
  /** A stand-in for one page: it renders its name as the page heading. */
  pageStub: (name: string) =>
    function PageStub() {
      return <h1>{name}</h1>;
    },
}));

vi.mock('../features/auth', () => ({
  ChangePasswordPage: pageStub('Change password'),
  ForgotPasswordPage: pageStub('Forgot password'),
  LoginPage: pageStub('Sign in'),
  ResetPasswordPage: pageStub('Reset password'),
}));
vi.mock('../features/dashboard/DashboardPage', () => ({
  DashboardPage: pageStub('Dashboard'),
}));
vi.mock('../features/join/JoinWizard', () => ({ JoinWizard: pageStub('Join CalDART') }));
vi.mock('../features/join/RenewPage', () => ({ RenewPage: pageStub('Renew') }));
vi.mock('../features/profile/ProfilePage', () => ({ ProfilePage: pageStub('My profile') }));
vi.mock('../features/profile/MyAircraftPage', () => ({ MyAircraftPage: pageStub('My aircraft') }));
vi.mock('../features/payments/PaymentsPage', () => ({ PaymentsPage: pageStub('My payments') }));
vi.mock('../features/leader/LeaderSearchPage', () => ({
  LeaderSearchPage: pageStub('Member check'),
}));
vi.mock('../features/leader/LeaderAircraftPage', () => ({
  LeaderAircraftPage: pageStub('Aircraft check'),
}));
vi.mock('../features/admin-members/MembersListPage', () => ({
  MembersListPage: pageStub('Members'),
}));
vi.mock('../features/admin-members/MemberCreatePage', () => ({
  MemberCreatePage: pageStub('Add a member'),
}));
vi.mock('../features/admin-members/MemberDetailPage', () => ({
  MemberDetailPage: pageStub('Member record'),
}));
vi.mock('../features/admin-aircraft/AircraftRegisterPage', () => ({
  AircraftRegisterPage: pageStub('Aircraft register'),
}));
vi.mock('../features/admin-aircraft/AircraftRecordPage', () => ({
  AircraftRecordPage: pageStub('Aircraft record'),
}));
vi.mock('../features/admin-payments/AdminPaymentsPage', () => ({
  AdminPaymentsPage: pageStub('Payments'),
}));
vi.mock('../features/admin-payments/PaymentsListPage', () => ({
  PaymentsListPage: pageStub('All payments'),
}));
vi.mock('../features/admin-payments/PaymentDetailPage', () => ({
  PaymentDetailPage: pageStub('Payment record'),
}));
vi.mock('../features/admin-payments/RecordPaymentPage', () => ({
  RecordPaymentPage: pageStub('Record a payment'),
}));
vi.mock('../features/admin-payments/MemberLedgerPage', () => ({
  MemberLedgerPage: pageStub('Member ledger'),
}));
vi.mock('../features/admin-reminders/AdminRemindersPage', () => ({
  AdminRemindersPage: pageStub('Reminders'),
}));
vi.mock('../features/admin-users/UsersListPage', () => ({
  UsersListPage: pageStub('Users and roles'),
}));
vi.mock('../features/admin-users/UserDetailPage', () => ({
  UserDetailPage: pageStub('User record'),
}));
vi.mock('../features/system/SystemPage', () => ({ SystemPage: pageStub('System') }));

/** The 403 page's headline, from `auth/guards.tsx`. */
const FORBIDDEN = 'You do not have access to this page';

interface Identity {
  /** How the case is named, and the key the `allowed` lists use. */
  name: string;
  roles: RoleSlug[];
}

/**
 * Every signed-in identity the table is checked against.  Each administrator
 * also holds `member`, as the real accounts do.
 */
const IDENTITIES: Identity[] = [
  { name: 'no roles', roles: [] },
  { name: 'member', roles: ['member'] },
  { name: 'dart_leader', roles: ['member', 'dart_leader'] },
  { name: 'user_admin', roles: ['member', 'user_admin'] },
  { name: 'treasurer', roles: ['member', 'treasurer'] },
  { name: 'account_admin', roles: ['member', 'account_admin'] },
  { name: 'website_admin', roles: ['member', 'website_admin'] },
  { name: 'system_admin', roles: ['member', 'system_admin'] },
];

/** The identity names of every entry in `IDENTITIES`: open to anyone signed in. */
const ANY_SIGNED_IN = [
  'no roles',
  'member',
  'dart_leader',
  'user_admin',
  'treasurer',
  'account_admin',
  'website_admin',
  'system_admin',
];

interface GuardedPath {
  path: string;
  /** The heading the page's stub renders. */
  heading: string;
  /** Identity names that reach the page; every other identity gets the 403 page. */
  allowed: string[];
}

const GUARDED_PATHS: GuardedPath[] = [
  { path: '/', heading: 'Dashboard', allowed: ANY_SIGNED_IN },
  { path: '/profile', heading: 'My profile', allowed: ANY_SIGNED_IN },
  { path: '/profile/aircraft', heading: 'My aircraft', allowed: ANY_SIGNED_IN },
  { path: '/payments', heading: 'My payments', allowed: ANY_SIGNED_IN },
  { path: '/renew', heading: 'Renew', allowed: ANY_SIGNED_IN },
  { path: '/change-password', heading: 'Change password', allowed: ANY_SIGNED_IN },
  {
    path: '/leader',
    heading: 'Member check',
    allowed: ['dart_leader', 'account_admin', 'system_admin'],
  },
  {
    path: '/leader/aircraft',
    heading: 'Aircraft check',
    allowed: ['dart_leader', 'account_admin', 'system_admin'],
  },
  { path: '/admin/members', heading: 'Members', allowed: ['account_admin', 'system_admin'] },
  {
    path: '/admin/members/new',
    heading: 'Add a member',
    allowed: ['account_admin', 'system_admin'],
  },
  {
    path: '/admin/members/1',
    heading: 'Member record',
    allowed: ['account_admin', 'system_admin'],
  },
  {
    path: '/admin/aircraft',
    heading: 'Aircraft register',
    allowed: ['account_admin', 'system_admin'],
  },
  {
    path: '/admin/aircraft/1',
    heading: 'Aircraft record',
    allowed: ['account_admin', 'system_admin'],
  },
  {
    path: '/admin/payments',
    heading: 'Payments',
    allowed: ['account_admin', 'treasurer', 'system_admin'],
  },
  {
    path: '/admin/payments/list',
    heading: 'All payments',
    allowed: ['account_admin', 'treasurer', 'system_admin'],
  },
  {
    path: '/admin/payments/record',
    heading: 'Record a payment',
    allowed: ['account_admin', 'treasurer', 'system_admin'],
  },
  {
    path: '/admin/payments/members/1',
    heading: 'Member ledger',
    allowed: ['account_admin', 'treasurer', 'system_admin'],
  },
  {
    path: '/admin/payments/412',
    heading: 'Payment record',
    allowed: ['account_admin', 'treasurer', 'system_admin'],
  },
  { path: '/admin/reminders', heading: 'Reminders', allowed: ['account_admin', 'system_admin'] },
  { path: '/admin/users', heading: 'Users and roles', allowed: ['user_admin', 'system_admin'] },
  { path: '/admin/users/1', heading: 'User record', allowed: ['user_admin', 'system_admin'] },
  { path: '/system', heading: 'System', allowed: ['system_admin'] },
];

interface RouteCase {
  path: string;
  heading: string;
  identity: string;
  roles: RoleSlug[];
}

function casesWhere(isAllowed: boolean): RouteCase[] {
  return GUARDED_PATHS.flatMap(({ path, heading, allowed }) =>
    IDENTITIES.filter((identity) => allowed.includes(identity.name) === isAllowed).map(
      (identity) => ({ path, heading, identity: identity.name, roles: identity.roles }),
    ),
  );
}

describe('the guarded paths', () => {
  it.each(GUARDED_PATHS)(
    '$path sends an anonymous visitor to the sign-in page',
    async ({ path }) => {
      const { router } = renderRoutes(routes, { route: path });

      await waitFor(() =>
        expect(`${router.state.location.pathname}${router.state.location.search}`).toBe(
          `/login?next=${encodeURIComponent(path)}`,
        ),
      );
    },
  );

  it.each(casesWhere(true))('$path opens for $identity', async ({ path, heading, roles }) => {
    server.use(signedInAs(makeUser({ roles })));

    renderRoutes(routes, { route: path });

    expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument();
  });

  it.each(casesWhere(false))('$path refuses $identity', async ({ path, roles }) => {
    server.use(signedInAs(makeUser({ roles })));

    renderRoutes(routes, { route: path });

    expect(await screen.findByText(FORBIDDEN)).toBeInTheDocument();
  });
});

describe('the paths outside the session', () => {
  it('renders the sign-in page for an anonymous visitor', async () => {
    renderRoutes(routes, { route: '/login' });

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('renders the join wizard for an anonymous visitor', async () => {
    renderRoutes(routes, { route: '/join' });

    expect(await screen.findByRole('heading', { name: 'Join CalDART' })).toBeInTheDocument();
  });

  it('renders the not-found page for an unknown path', async () => {
    renderRoutes(routes, { route: '/no-such-screen' });

    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });

  it('has no address that ends a session: /logout is not a route', async () => {
    server.use(signedInAs(makeUser()));

    renderRoutes(routes, { route: '/logout' });

    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});

describe('the routes that load on demand', () => {
  it('shows the loading indicator until the first page asked for has arrived', () => {
    renderRoutes(routes, { route: '/join' });

    expect(screen.getByRole('status')).toHaveTextContent('Loading');
  });

  it('leaves the eager landing screens ready on the first render', () => {
    renderRoutes(routes, { route: '/login' });

    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });
});
