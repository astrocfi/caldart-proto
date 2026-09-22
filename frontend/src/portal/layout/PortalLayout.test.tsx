/**
 * The portal chrome, and the one control that ends a session.
 *
 * Signing out is a button that posts, not an address that can be opened, so
 * merely rendering the shell must never log anybody out.
 */
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes } from 'react-router-dom';
import type { RouteObject } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { API, makeUser, signedInAs } from '@test/handlers';
import { renderRoutes, renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { RoleSlug } from '../api/types';
import { PortalLayout } from './PortalLayout';

/** The layout with one routed child, so the outlet has something to render. */
function tree() {
  return (
    <Routes>
      <Route element={<PortalLayout />}>
        <Route path="/" element={<p>dashboard body</p>} />
        <Route path="/profile" element={<p>profile body</p>} />
      </Route>
    </Routes>
  );
}

/** The accessible names of the links in the portal rail, in render order. */
function railLinkNames(): string[] {
  const rail = screen.getByRole('navigation', { name: 'Portal sections' });
  return within(rail)
    .getAllByRole('link')
    .map((link) => link.textContent ?? '');
}

describe('PortalLayout', () => {
  it('renders the routed page in the main landmark', async () => {
    server.use(signedInAs(makeUser()));
    renderWithProviders(tree(), { route: '/profile' });

    expect(await screen.findByText('profile body')).toBeInTheDocument();
    expect(within(screen.getByRole('main')).getByText('profile body')).toBeInTheDocument();
  });

  it('offers a skip link straight to the main landmark', () => {
    renderWithProviders(tree(), { route: '/' });

    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute(
      'href',
      '#portal-main',
    );
    expect(screen.getByRole('main')).toHaveAttribute('id', 'portal-main');
  });

  it('shows a plain member only the Membership group', async () => {
    server.use(signedInAs(makeUser({ roles: ['member'] })));
    renderWithProviders(tree(), { route: '/' });

    await screen.findByRole('navigation', { name: 'Portal sections' });
    expect(railLinkNames()).toEqual([
      'Dashboard',
      'My profile',
      'My aircraft',
      'Renew',
      'Change password',
      'Back to caldart.org',
    ]);
  });

  it.each<[RoleSlug, string[]]>([
    ['dart_leader', ['Member check', 'Aircraft check']],
    ['account_admin', ['Member check', 'Aircraft check', 'Members', 'Aircraft', 'Payments']],
    ['user_admin', ['Users & roles']],
    ['system_admin', ['System']],
  ])('adds the %s entries to the rail', async (role, expected) => {
    server.use(signedInAs(makeUser({ roles: ['member', role] })));
    renderWithProviders(tree(), { route: '/' });

    await screen.findByRole('navigation', { name: 'Portal sections' });
    const names = railLinkNames();
    for (const label of expected) {
      expect(names).toContain(label);
    }
  });

  it('hides a privileged entry from the role that does not hold it', async () => {
    server.use(signedInAs(makeUser({ roles: ['member', 'dart_leader'] })));
    renderWithProviders(tree(), { route: '/' });

    await screen.findByRole('navigation', { name: 'Portal sections' });
    expect(railLinkNames()).not.toContain('Users & roles');
  });

  it('gives an anonymous visitor no rail at all', async () => {
    renderWithProviders(tree(), { route: '/' });

    expect(await screen.findByText('dashboard body')).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Portal sections' })).not.toBeInTheDocument();
  });

  it('offers an anonymous visitor a way to sign in instead of an identity', async () => {
    renderWithProviders(tree(), { route: '/' });

    expect(await screen.findByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login');
  });

  it('names the signed-in user in the header', async () => {
    server.use(signedInAs(makeUser({ email: 'marta@example.org' })));
    renderWithProviders(tree(), { route: '/' });

    expect(await screen.findByText('marta@example.org')).toBeInTheDocument();
  });

  it('opens and closes the mobile drawer from the Menu button', async () => {
    const user = userEvent.setup();
    server.use(signedInAs(makeUser()));
    renderWithProviders(tree(), { route: '/' });

    const menu = await screen.findByRole('button', { name: 'Menu' });
    expect(menu).toHaveAttribute('aria-expanded', 'false');
    expect(menu).toHaveAttribute('aria-controls', 'portal-nav');

    await user.click(menu);
    expect(menu).toHaveAttribute('aria-expanded', 'true');

    await user.click(menu);
    expect(menu).toHaveAttribute('aria-expanded', 'false');
  });

  it('closes the drawer as soon as the visitor navigates', async () => {
    const user = userEvent.setup();
    server.use(signedInAs(makeUser()));
    renderWithProviders(tree(), { route: '/' });

    const menu = await screen.findByRole('button', { name: 'Menu' });
    await user.click(menu);
    expect(menu).toHaveAttribute('aria-expanded', 'true');

    await user.click(screen.getByRole('link', { name: 'My profile' }));

    expect(await screen.findByText('profile body')).toBeInTheDocument();
    expect(menu).toHaveAttribute('aria-expanded', 'false');
  });

  it('gives an anonymous visitor no drawer toggle', async () => {
    renderWithProviders(tree(), { route: '/' });

    expect(await screen.findByText('dashboard body')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Menu' })).not.toBeInTheDocument();
  });

  it('marks the entry for the open page as the current one', async () => {
    server.use(signedInAs(makeUser()));
    renderWithProviders(tree(), { route: '/profile' });

    const link = await screen.findByRole('link', { name: 'My profile' });
    expect(link).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute('aria-current');
  });
});

function DashboardStub() {
  return <h1>Dashboard</h1>;
}

function LoginStub() {
  return <h1>Sign in</h1>;
}

const routes: RouteObject[] = [
  { path: '/', element: <PortalLayout />, children: [{ index: true, element: <DashboardStub /> }] },
  { path: '/login', element: <LoginStub /> },
];

/** Count `POST /auth/logout` calls, and make `/auth/me` anonymous afterwards. */
function countLogouts(): { calls: number } {
  const counter = { calls: 0 };
  server.use(
    http.post(`${API}/auth/logout`, () => {
      counter.calls += 1;
      server.use(
        http.get(`${API}/auth/me`, () =>
          HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 }),
        ),
      );
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return counter;
}

describe('<PortalLayout/> sign out', () => {
  it('offers sign out as a button rather than a link', async () => {
    server.use(signedInAs(makeUser()));

    renderRoutes(routes);

    expect(await screen.findByRole('button', { name: 'Sign out' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Sign out' })).not.toBeInTheDocument();
  });

  it('leaves the session alone until the button is pressed', async () => {
    server.use(signedInAs(makeUser()));
    const logouts = countLogouts();

    renderRoutes(routes);

    expect(await screen.findByRole('button', { name: 'Sign out' })).toBeInTheDocument();
    expect(logouts.calls).toBe(0);
  });

  it('posts to the logout endpoint exactly once when the button is pressed', async () => {
    const user = userEvent.setup();
    server.use(signedInAs(makeUser()));
    const logouts = countLogouts();

    renderRoutes(routes);
    await user.click(await screen.findByRole('button', { name: 'Sign out' }));

    await waitFor(() => expect(logouts.calls).toBe(1));
  });

  it('lands on the sign-in page once the session has ended', async () => {
    const user = userEvent.setup();
    server.use(signedInAs(makeUser()));
    countLogouts();

    const { router } = renderRoutes(routes);
    await user.click(await screen.findByRole('button', { name: 'Sign out' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/login'));
  });

  it('empties the query cache on the way out', async () => {
    const user = userEvent.setup();
    server.use(signedInAs(makeUser()));
    countLogouts();

    const { client } = renderRoutes(routes);
    await screen.findByRole('button', { name: 'Sign out' });
    client.setQueryData(['admin', 'members'], ['someone else was here']);

    await user.click(screen.getByRole('button', { name: 'Sign out' }));

    await waitFor(() => expect(client.getQueryData(['admin', 'members'])).toBeUndefined());
  });

  it('shows the signed-in address beside the button', async () => {
    server.use(signedInAs(makeUser({ email: 'marta@example.org' })));

    renderRoutes(routes);

    expect(await screen.findByText('marta@example.org')).toBeInTheDocument();
  });

  it('offers sign in instead when nobody is signed in', async () => {
    renderRoutes(routes);

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sign in' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
  });
});
