import { act, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';
import { Route, Routes, useSearchParams } from 'react-router-dom';

import { API, makeUser, signedInAs } from '../../test/handlers';
import { renderWithProviders } from '../../test/render';
import { server } from '../../test/server';
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

  it('redirects an anonymous visitor to /login with a next parameter', async () => {
    renderWithProviders(
      tree(
        <RequireAuth>
          <Secret />
        </RequireAuth>,
      ),
      { route: '/secret' },
    );
    expect(await screen.findByText('login page')).toBeInTheDocument();
    expect(screen.queryByText('secret content')).not.toBeInTheDocument();
  });
});

describe('RequireRole', () => {
  it('renders for a user holding the role', async () => {
    server.use(signedInAs(makeUser({ roles: ['member', 'dart_leader'] })));
    renderWithProviders(
      tree(
        <RequireRole roles={['dart_leader']}>
          <Secret />
        </RequireRole>,
      ),
      { route: '/secret' },
    );
    expect(await screen.findByText('secret content')).toBeInTheDocument();
  });

  it('shows a 403 page for a user without the role', async () => {
    server.use(signedInAs(makeUser({ roles: ['member'] })));
    renderWithProviders(
      tree(
        <RequireRole roles={['account_admin']}>
          <Secret />
        </RequireRole>,
      ),
      { route: '/secret' },
    );
    expect(await screen.findByText(/do not have access/i)).toBeInTheDocument();
    expect(screen.queryByText('secret content')).not.toBeInTheDocument();
  });

  it('lets a system_admin through any role gate', async () => {
    server.use(signedInAs(makeUser({ roles: ['system_admin'] })));
    renderWithProviders(
      tree(
        <RequireRole roles={['account_admin']}>
          <Secret />
        </RequireRole>,
      ),
      { route: '/secret' },
    );
    expect(await screen.findByText('secret content')).toBeInTheDocument();
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
    expect(await screen.findByText(/open to the user admin role/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /go to the dashboard/i })).toBeInTheDocument();
  });
});

describe('the next parameter', () => {
  it('points back at the guarded page', async () => {
    renderWithProviders(
      tree(
        <RequireAuth>
          <Secret />
        </RequireAuth>,
      ),
      { route: '/secret' },
    );
    expect(await screen.findByText('next=/secret')).toBeInTheDocument();
  });
});
