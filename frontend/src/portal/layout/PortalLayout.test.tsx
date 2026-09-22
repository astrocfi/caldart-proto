/**
 * The portal chrome, and the one control that ends a session.
 *
 * Signing out is a button that posts, not an address that can be opened, so
 * merely rendering the shell must never log anybody out.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import type { RouteObject } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { API, makeUser, signedInAs } from '../../test/handlers';
import { renderRoutes } from '../../test/render';
import { server } from '../../test/server';
import { PortalLayout } from './PortalLayout';

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

    expect(await screen.findByRole('link', { name: 'Sign in' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
  });
});
