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
import { FINANCE_TABS } from '../features/admin-payments/FinanceTabs';
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
vi.mock('../features/auth/ChangeEmailPage', () => ({
  ChangeEmailPage: pageStub('Change email'),
}));
vi.mock('../features/auth/VerifyEmailPage', () => ({
  VerifyEmailPage: pageStub('Verify email'),
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
  AircraftRegisterPage: pageStub('Aircraft'),
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
vi.mock('../features/admin-payments/RenewalsPage', () => ({
  RenewalsPage: pageStub('Renewals'),
}));
vi.mock('../features/admin-payments/ReconciliationPage', () => ({
  ReconciliationPage: pageStub('Reconciliation'),
}));
vi.mock('../features/admin-payments/ContributionsPage', () => ({
  ContributionsPage: pageStub('Contributions'),
}));
vi.mock('../features/admin-payments/DonorsPage', () => ({
  DonorsPage: pageStub('Donors'),
}));
vi.mock('../features/admin-reminders/AdminRemindersPage', () => ({
  AdminRemindersPage: pageStub('Reminders'),
}));
vi.mock('../features/admin-reports/AdminReportsPage', () => ({
  AdminReportsPage: pageStub('Subscriptions'),
}));
vi.mock('../features/admin-notifications/AdminNotificationsPage', () => ({
  AdminNotificationsPage: pageStub('Notification emails'),
}));
vi.mock('../features/bulk-email/ComposeStart', () => ({
  ComposeStart: pageStub('Compose'),
}));
vi.mock('../features/bulk-email/ComposePage', () => ({
  ComposePage: pageStub('Compose a bulk email'),
}));
vi.mock('../features/bulk-email/DraftsPage', () => ({
  DraftsPage: pageStub('Drafts and scheduled'),
}));
vi.mock('../features/bulk-email/SentPage', () => ({ SentPage: pageStub('Sent') }));
vi.mock('../features/bulk-email/SentDetailPage', () => ({
  SentDetailPage: pageStub('Sent bulk email'),
}));
vi.mock('../features/bulk-email/TemplatesPage', () => ({
  TemplatesPage: pageStub('Templates'),
}));
vi.mock('../features/bulk-email/GroupsPage', () => ({
  GroupsPage: pageStub('Recipient groups'),
}));
vi.mock('../features/bulk-email/GroupDetailPage', () => ({
  GroupDetailPage: pageStub('Recipient group'),
}));
vi.mock('../features/email-types/EmailTypesPage', () => ({
  EmailTypesPage: pageStub('Email types'),
}));
vi.mock('../features/messages/MessagesPage', () => ({ MessagesPage: pageStub('Email to me') }));
vi.mock('../features/messages/MessagePage', () => ({ MessagePage: pageStub('Message') }));
vi.mock('../features/email-preferences/EmailPreferencesPage', () => ({
  EmailPreferencesPage: pageStub('Email preferences'),
}));
vi.mock('../features/donate/DonatePage', () => ({ DonatePage: pageStub('Donate') }));
vi.mock('../features/callouts/CalloutsPage', () => ({
  CalloutsPage: pageStub('Callouts'),
}));
vi.mock('../features/callouts/CalloutDetailPage', () => ({
  CalloutDetailPage: pageStub('Callout'),
}));
vi.mock('../features/admin-users/UsersListPage', () => ({
  UsersListPage: pageStub('Roles and status'),
}));
vi.mock('../features/admin-users/UserDetailPage', () => ({
  UserDetailPage: pageStub('User record'),
}));
vi.mock('../features/system/HealthDatabasePage', () => ({
  HealthDatabasePage: pageStub('Health and database'),
}));
vi.mock('../features/system/SentEmailsPage', () => ({ SentEmailsPage: pageStub('Sent emails') }));
vi.mock('../features/system/ScheduledPage', () => ({ ScheduledPage: pageStub('Scheduled tasks') }));

/** The 403 page's headline, from `auth/guards.tsx`. */
const FORBIDDEN = /^You do not have access to this page\./;

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
  { name: 'verifier', roles: ['member', 'verifier'] },
  { name: 'dart_leader', roles: ['member', 'dart_leader'] },
  { name: 'user_admin', roles: ['member', 'user_admin'] },
  { name: 'treasurer', roles: ['member', 'treasurer'] },
  { name: 'account_admin', roles: ['member', 'account_admin'] },
  { name: 'management', roles: ['member', 'management'] },
  { name: 'website_admin', roles: ['member', 'website_admin'] },
  { name: 'system_admin', roles: ['member', 'system_admin'] },
];

/** The identity names of every entry in `IDENTITIES`: open to anyone signed in. */
const ANY_SIGNED_IN = [
  'no roles',
  'member',
  'verifier',
  'dart_leader',
  'user_admin',
  'treasurer',
  'account_admin',
  'management',
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
  { path: '/donate', heading: 'Donate', allowed: ANY_SIGNED_IN },
  { path: '/renew', heading: 'Renew', allowed: ANY_SIGNED_IN },
  { path: '/change-password', heading: 'Change password', allowed: ANY_SIGNED_IN },
  { path: '/change-email', heading: 'Change email', allowed: ANY_SIGNED_IN },
  {
    path: '/leader',
    heading: 'Member check',
    allowed: ['verifier', 'dart_leader', 'user_admin', 'account_admin', 'system_admin'],
  },
  {
    path: '/leader/aircraft',
    heading: 'Aircraft check',
    allowed: ['verifier', 'dart_leader', 'user_admin', 'account_admin', 'system_admin'],
  },
  {
    path: '/admin/members',
    heading: 'Members',
    allowed: ['account_admin', 'dart_leader', 'system_admin'],
  },
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
    heading: 'Aircraft',
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
    path: '/admin/payments/renewals',
    heading: 'Renewals',
    allowed: ['account_admin', 'treasurer', 'system_admin'],
  },
  {
    path: '/admin/payments/reconciliation',
    heading: 'Reconciliation',
    allowed: ['account_admin', 'treasurer', 'system_admin'],
  },
  {
    path: '/admin/payments/contributions',
    heading: 'Contributions',
    allowed: ['account_admin', 'treasurer', 'system_admin'],
  },
  {
    path: '/admin/payments/donors',
    heading: 'Donors',
    allowed: ['treasurer', 'system_admin'],
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
  {
    path: '/admin/reports',
    heading: 'Subscriptions',
    allowed: ['account_admin', 'treasurer', 'system_admin'],
  },
  {
    path: '/admin/notifications',
    heading: 'Notification emails',
    allowed: ['account_admin', 'system_admin'],
  },
  {
    path: '/bulk-email/compose',
    heading: 'Compose',
    allowed: ['dart_leader', 'management', 'system_admin'],
  },
  {
    path: '/bulk-email/drafts',
    heading: 'Drafts and scheduled',
    allowed: ['dart_leader', 'management', 'system_admin'],
  },
  {
    path: '/bulk-email/compose/1',
    heading: 'Compose a bulk email',
    allowed: ['dart_leader', 'management', 'system_admin'],
  },
  {
    path: '/bulk-email/sent',
    heading: 'Sent',
    allowed: ['dart_leader', 'management', 'system_admin'],
  },
  {
    path: '/bulk-email/sent/1',
    heading: 'Sent bulk email',
    allowed: ['dart_leader', 'management', 'system_admin'],
  },
  {
    path: '/bulk-email/callouts',
    heading: 'Callouts',
    allowed: ['dart_leader', 'management', 'system_admin'],
  },
  {
    path: '/bulk-email/callouts/1',
    heading: 'Callout',
    allowed: ['dart_leader', 'management', 'system_admin'],
  },
  {
    path: '/bulk-email/templates',
    heading: 'Templates',
    allowed: ['management', 'system_admin'],
  },
  {
    path: '/bulk-email/groups',
    heading: 'Recipient groups',
    allowed: ['management', 'system_admin'],
  },
  {
    path: '/bulk-email/groups/1',
    heading: 'Recipient group',
    allowed: ['management', 'system_admin'],
  },
  { path: '/bulk-email/types', heading: 'Email types', allowed: ['system_admin'] },
  { path: '/messages', heading: 'Email to me', allowed: ANY_SIGNED_IN },
  { path: '/messages/1', heading: 'Message', allowed: ANY_SIGNED_IN },
  { path: '/email-preferences', heading: 'Email preferences', allowed: ANY_SIGNED_IN },
  { path: '/admin/users', heading: 'Roles and status', allowed: ['user_admin', 'system_admin'] },
  { path: '/admin/users/1', heading: 'User record', allowed: ['user_admin', 'system_admin'] },
  { path: '/system', heading: 'Health and database', allowed: ['system_admin'] },
  {
    path: '/bulk-email/mail-delivery',
    heading: 'Health and database',
    allowed: ['system_admin'],
  },
  { path: '/system/health', heading: 'Health and database', allowed: ['system_admin'] },
  { path: '/system/emails', heading: 'Sent emails', allowed: ['system_admin'] },
  { path: '/system/scheduled', heading: 'Scheduled tasks', allowed: ['system_admin'] },
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

describe('the finance area', () => {
  it('gives every tab a route a treasurer may open', () => {
    const openToTreasurer = GUARDED_PATHS.filter((guarded) =>
      guarded.allowed.includes('treasurer'),
    ).map((guarded) => guarded.path);

    expect(openToTreasurer).toEqual(expect.arrayContaining(FINANCE_TABS.map((tab) => tab.to)));
  });
});

describe('the System section', () => {
  it('sends a system administrator at /system to Health and database', async () => {
    server.use(signedInAs(makeUser({ roles: ['member', 'system_admin'] })));

    const { router } = renderRoutes(routes, { route: '/system' });

    await waitFor(() => expect(router.state.location.pathname).toBe('/system/health'));
  });
});

describe('the paths outside the session', () => {
  it('renders the sign-in page for an anonymous visitor', async () => {
    renderRoutes(routes, { route: '/login' });

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('renders the verify-email page for an anonymous visitor', async () => {
    renderRoutes(routes, { route: '/verify-email?token=abc' });

    expect(await screen.findByRole('heading', { name: 'Verify email' })).toBeInTheDocument();
  });

  it('renders the join wizard for an anonymous visitor', async () => {
    renderRoutes(routes, { route: '/join' });

    expect(await screen.findByRole('heading', { name: 'Join CalDART' })).toBeInTheDocument();
  });

  it('renders the not-found page for an unknown path', async () => {
    renderRoutes(routes, { route: '/no-such-screen' });

    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });

  it('sends a signed-out visitor from the not-found page to the CalDART home page', async () => {
    renderRoutes(routes, { route: '/no-such-screen' });

    expect(
      await screen.findByRole('link', { name: 'Go to the CalDART home page' }),
    ).toHaveAttribute('href', '/');
  });

  it('offers a signed-out visitor no dashboard from the not-found page', async () => {
    renderRoutes(routes, { route: '/no-such-screen' });

    await screen.findByRole('link', { name: 'Go to the CalDART home page' });
    expect(screen.queryByRole('link', { name: 'Go to the dashboard' })).not.toBeInTheDocument();
  });

  it('sends a signed-in member from the not-found page to their dashboard', async () => {
    server.use(signedInAs(makeUser()));
    renderRoutes(routes, { route: '/no-such-screen' });

    expect(await screen.findByRole('link', { name: 'Go to the dashboard' })).toHaveAttribute(
      'href',
      '/',
    );
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

describe('the onboarding gate', () => {
  const UNVERIFIED = makeUser({ email_verified: false });

  it.each(['/', '/profile', '/payments', '/renew', '/change-password'])(
    '%s sends a reader with an unverified address to the verify step',
    async (path) => {
      server.use(signedInAs(UNVERIFIED));

      const { router } = renderRoutes(routes, { route: path });

      await waitFor(() => expect(router.state.location.pathname).toBe('/join/verify'));
    },
  );

  it('sends a reader with an incomplete profile to the profile step', async () => {
    server.use(signedInAs(makeUser({ profile_complete: false })));

    const { router } = renderRoutes(routes, { route: '/' });

    await waitFor(() => expect(router.state.location.pathname).toBe('/join/profile'));
  });

  it('leaves the change-email page open, so a mistyped address can be corrected', async () => {
    server.use(signedInAs(UNVERIFIED));

    renderRoutes(routes, { route: '/change-email' });

    expect(await screen.findByRole('heading', { name: 'Change email' })).toBeInTheDocument();
  });

  it('leaves the verify-email page open to a reader following the link', async () => {
    server.use(signedInAs(UNVERIFIED));

    renderRoutes(routes, { route: '/verify-email?token=abc' });

    expect(await screen.findByRole('heading', { name: 'Verify email' })).toBeInTheDocument();
  });
});
