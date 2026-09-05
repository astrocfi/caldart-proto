import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Route, Routes } from 'react-router-dom';

import { makeUser, signedInAs } from '../../test/handlers';
import { renderWithProviders } from '../../test/render';
import { server } from '../../test/server';
import { RequireAuth, RequireRole } from './guards';

function Secret() {
  return <p>secret content</p>;
}

function LoginStub() {
  return <p>login page</p>;
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
