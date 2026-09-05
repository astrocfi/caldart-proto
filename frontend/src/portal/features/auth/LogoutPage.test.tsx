import { screen } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { API, makeUser, signedInAs } from '../../../test/handlers';
import { makeTestQueryClient, renderWithProviders } from '../../../test/render';
import { server } from '../../../test/server';
import { LogoutPage } from './LogoutPage';

function LoginStub() {
  return <h1>Sign in</h1>;
}

function tree() {
  return (
    <Routes>
      <Route path="/logout" element={<LogoutPage />} />
      <Route path="/login" element={<LoginStub />} />
    </Routes>
  );
}

describe('LogoutPage', () => {
  it('calls the API, empties the cache and lands on sign in', async () => {
    let calls = 0;
    server.use(
      signedInAs(makeUser()),
      http.post(`${API}/auth/logout`, () => {
        calls += 1;
        server.use(
          http.get(`${API}/auth/me`, () =>
            HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 }),
          ),
        );
        return new HttpResponse(null, { status: 204 });
      }),
    );

    const client = makeTestQueryClient();
    client.setQueryData(['admin', 'users', {}], { count: 1, results: [makeUser()] });

    renderWithProviders(tree(), { route: '/logout', client });

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
    expect(calls).toBe(1);
    expect(client.getQueryData(['admin', 'users', {}])).toBeUndefined();
  });

  it('goes straight to sign in when nobody is signed in', async () => {
    renderWithProviders(tree(), { route: '/logout' });
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });
});
