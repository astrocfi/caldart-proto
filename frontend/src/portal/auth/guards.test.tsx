import { act, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';
import { Route, Routes, useSearchParams } from 'react-router-dom';

import type { RoleSlug } from '../api/types';
import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { RequireAuth, RequireRole, loginRedirect } from './guards';
import { AUTH_ME_KEY } from './useAuth';

/** `/auth/me` answers 500, as it does while the backend is restarting. */
function meIsDown() {
  return http.get(`${API}/auth/me`, () =>
    HttpResponse.json({ detail: 'Server error' }, { status: 500 }),
  );
}

function Secret() {
  return <p>secret content</p>;
}

function LoginStub() {
  const [params] = useSearchParams();
  return (
    <>
      <p>login page</p>
      <p>next={params.get('next')}</p>
    </>
  );
}

function tree(guard: React.ReactNode) {
  return (
    <Routes>
      <Route path="/login" element={<LoginStub />} />
      <Route path="/secret" element={guard} />
    </Routes>
  );
}

describe('RequireAuth', () => {
  it('renders the child once the user is known', async () => {
    server.use(signedInAs(makeUser()));
    renderWithProviders(
      tree(
        <RequireAuth>
          <Secret />
        </RequireAuth>,
      ),
      { route: '/secret' },
    );
    expect(await screen.findByText('secret content')).toBeInTheDocument();
  });

  it('redirects an anonymous visitor to /login, pointing next at the guarded page', async () => {
    renderWithProviders(
      tree(
        <RequireAuth>
          <Secret />
        </RequireAuth>,
      ),
      { route: '/secret' },
    );
    expect(await screen.findByText('login page')).toBeInTheDocument();
    expect(screen.getByText('next=/secret')).toBeInTheDocument();
    expect(screen.queryByText('secret content')).not.toBeInTheDocument();
  });
});

describe('RequireRole', () => {
  /** Render `<RequireRole roles={gate}>` for a user holding `roles`. */
  function renderGate(roles: RoleSlug[], gate: RoleSlug[]) {
    server.use(signedInAs(makeUser({ roles })));
    return renderWithProviders(
      tree(
        <RequireRole roles={gate}>
          <Secret />
        </RequireRole>,
      ),
      { route: '/secret' },
    );
  }

  // The last case is the rule that a system admin holds every gate open,
  // whatever role that gate names.
  it.each<[RoleSlug[], RoleSlug[]]>([
    [['member', 'dart_leader'], ['dart_leader']],
    [['account_admin'], ['account_admin']],
    [['user_admin'], ['user_admin']],
    [['website_admin'], ['website_admin']],
    [
      ['member', 'account_admin'],
      ['dart_leader', 'account_admin'],
    ],
    [['system_admin'], ['account_admin']],
  ])('renders the page for %s behind a %s gate', async (roles, gate) => {
    renderGate(roles, gate);
    expect(await screen.findByText('secret content')).toBeInTheDocument();
  });

  it.each<[RoleSlug[], RoleSlug[]]>([
    [['member'], ['account_admin']],
    [['member'], ['dart_leader']],
    [['dart_leader'], ['user_admin']],
    [['account_admin'], ['system_admin']],
    [[], ['member']],
  ])('shows the 403 page for %s behind a %s gate', async (roles, gate) => {
    renderGate(roles, gate);
    expect(await screen.findByText(/do not have access/i)).toBeInTheDocument();
    expect(screen.queryByText('secret content')).not.toBeInTheDocument();
  });

  it('sends an anonymous visitor to login rather than 403', async () => {
    renderWithProviders(
      tree(
        <RequireRole roles={['account_admin']}>
          <Secret />
        </RequireRole>,
      ),
      { route: '/secret' },
    );
    expect(await screen.findByText('login page')).toBeInTheDocument();
  });
});

describe('a failed sign-in check', () => {
  it('shows an alert instead of the login page when /auth/me answers 500', async () => {
    server.use(meIsDown());
    renderWithProviders(
      tree(
        <RequireAuth>
          <Secret />
        </RequireAuth>,
      ),
      { route: '/secret' },
    );
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not check your sign-in/i);
  });

  it('does not send the visitor to login when /auth/me answers 500', async () => {
    server.use(meIsDown());
    renderWithProviders(
      tree(
        <RequireAuth>
          <Secret />
        </RequireAuth>,
      ),
      { route: '/secret' },
    );
    await screen.findByRole('alert');
    expect(screen.queryByText('login page')).not.toBeInTheDocument();
  });

  it('shows the alert under RequireRole when /auth/me fails at the network level', async () => {
    server.use(http.get(`${API}/auth/me`, () => HttpResponse.error()));
    renderWithProviders(
      tree(
        <RequireRole roles={['account_admin']}>
          <Secret />
        </RequireRole>,
      ),
      { route: '/secret' },
    );
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not check your sign-in/i);
  });

  it('renders the guarded page once Try again succeeds', async () => {
    let attempts = 0;
    server.use(
      http.get(`${API}/auth/me`, () => {
        attempts += 1;
        if (attempts === 1) return HttpResponse.json({ detail: 'Server error' }, { status: 500 });
        return HttpResponse.json(makeUser());
      }),
    );
    renderWithProviders(
      tree(
        <RequireAuth>
          <Secret />
        </RequireAuth>,
      ),
      { route: '/secret' },
    );
    await screen.findByRole('alert');

    await userEvent.click(screen.getByRole('button', { name: /try again/i }));

    expect(await screen.findByText('secret content')).toBeInTheDocument();
  });

  it('keeps the page for a signed-in user whose background refetch fails', async () => {
    server.use(signedInAs(makeUser()));
    const { client } = renderWithProviders(
      tree(
        <RequireAuth>
          <Secret />
        </RequireAuth>,
      ),
      { route: '/secret' },
    );
    await screen.findByText('secret content');

    server.use(meIsDown());
    await act(async () => {
      await client.refetchQueries({ queryKey: AUTH_ME_KEY });
    });

    expect(screen.getByText('secret content')).toBeInTheDocument();
  });
});

describe('loginRedirect', () => {
  it('carries the whole location, query string included', () => {
    expect(loginRedirect({ pathname: '/admin/users', search: '?role=user_admin' })).toBe(
      '/login?next=%2Fadmin%2Fusers%3Frole%3Duser_admin',
    );
  });
});

describe('the 403 page', () => {
  it('names the role the page wanted and offers a way out', async () => {
    server.use(signedInAs(makeUser({ roles: ['member'] })));
    renderWithProviders(
      tree(
        <RequireRole roles={['user_admin']}>
          <Secret />
        </RequireRole>,
      ),
      { route: '/secret' },
    );
    expect(await screen.findByText(/open to the User administrator role/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /go to the dashboard/i })).toBeInTheDocument();
  });
});
