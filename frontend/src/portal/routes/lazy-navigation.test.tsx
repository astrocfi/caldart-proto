/**
 * What a visitor sees while an on-demand page's module is still arriving.
 *
 * The root route's hydrate fallback covers the router's first load alone.  A
 * navigation made from inside the portal has no fallback: the router leaves
 * the current screen in place until the page's module resolves, and the portal
 * adds no progress indicator of its own.  The developer guide describes that,
 * so this file pins it.
 *
 * It stands apart from `index.test.tsx` because the page module mocked here
 * never arrives, which would strand every case that opens that path.
 */
import { act, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { makeUser, signedInAs } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import { routes } from './index';

vi.mock('../features/dashboard/DashboardPage', () => ({
  DashboardPage: function DashboardPage() {
    return <h1>Dashboard</h1>;
  },
}));

/** The members page never finishes loading, so the wait itself stays observable. */
vi.mock('../features/admin-members/MembersListPage', () => new Promise<never>(() => undefined));

/**
 * Open the dashboard as an account administrator, then start a navigation to
 * `/admin/members` and leave it waiting for that page's module.
 */
async function startNavigationToMembers(): Promise<void> {
  server.use(signedInAs(makeUser({ roles: ['member', 'account_admin'] })));
  const { router } = renderRoutes(routes, { route: '/' });
  expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();

  // `act` is handed an already-resolved promise rather than the navigation's
  // own, so React flushes its effects while the page module is still loading.
  await act(() => {
    void router.navigate('/admin/members');
    return Promise.resolve();
  });
  expect(router.state.navigation.state).toBe('loading');
}

describe('a navigation to a page that loads on demand', () => {
  it('leaves the current screen in place until the page module arrives', async () => {
    await startNavigationToMembers();

    expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
  });

  it('shows no loading indicator while the page module is on its way', async () => {
    await startNavigationToMembers();

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
