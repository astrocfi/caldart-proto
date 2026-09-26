import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { API, DEACTIVATED_LOGIN, makeUser, signInDeactivated } from '@test/handlers';
import { makeTestQueryClient, renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { AUTH_ME_KEY } from '@/portal/auth/useAuth';
import type * as guide from '@/portal/guide';
import { openGuide } from '@/portal/guide';
import { LoginPage, safeNext } from './LoginPage';

vi.mock('@/portal/guide', async (importOriginal: () => Promise<typeof guide>) => ({
  ...(await importOriginal()),
  openGuide: vi.fn(),
}));

function Dashboard() {
  return <h1>Dashboard</h1>;
}

function Profile() {
  return <h1>My profile</h1>;
}

/**
 * A query client that keeps what it is told, so a test can read the cache
 * after the page that observed it has gone.  The suite's default client
 * collects an unobserved query at once, which would hide the difference
 * between "cleared on sign-in" and "collected on unmount".
 */
function persistentClient() {
  const client = makeTestQueryClient();
  client.setDefaultOptions({
    queries: { retry: false, staleTime: 0, gcTime: Infinity },
    mutations: { retry: false },
  });
  return client;
}

function renderLogin(route = '/login') {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<Dashboard />} />
      <Route path="/profile" element={<Profile />} />
    </Routes>,
    { route },
  );
}

describe('safeNext', () => {
  it('keeps a same-site path', () => {
    expect(safeNext('/profile?tab=1')).toBe('/profile?tab=1');
  });

  it('falls back to the dashboard for anything else', () => {
    expect(safeNext(null)).toBe('/');
    expect(safeNext('https://evil.example')).toBe('/');
    expect(safeNext('//evil.example')).toBe('/');
  });
});

describe('LoginPage', () => {
  it('signs in and lands on the dashboard', async () => {
    const user = makeUser();
    let posted: unknown = null;
    server.use(
      http.post(`${API}/auth/login`, async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json(user);
      }),
    );

    renderLogin();
    await userEvent.type(await screen.findByLabelText(/email address/i), 'marta@example.org');
    await userEvent.type(screen.getByLabelText(/password/i), 'correct-horse');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
    expect(posted).toEqual({ email: 'marta@example.org', password: 'correct-horse' });
  });

  it('returns to the page the guard came from', async () => {
    server.use(http.post(`${API}/auth/login`, () => HttpResponse.json(makeUser())));

    renderLogin('/login?next=%2Fprofile');
    await userEvent.type(await screen.findByLabelText(/email address/i), 'marta@example.org');
    await userEvent.type(screen.getByLabelText(/password/i), 'correct-horse');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByRole('heading', { name: 'My profile' })).toBeInTheDocument();
  });

  it('leaves the portal for a guide page named by next', async () => {
    server.use(http.post(`${API}/auth/login`, () => HttpResponse.json(makeUser())));

    renderLogin('/login?next=%2Fdocs%2Fmember-guide%2F');
    await userEvent.type(await screen.findByLabelText(/email address/i), 'marta@example.org');
    await userEvent.type(screen.getByLabelText(/password/i), 'correct-horse');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => expect(openGuide).toHaveBeenCalledWith('/docs/member-guide/'));
    expect(screen.queryByRole('heading', { name: 'Dashboard' })).not.toBeInTheDocument();
  });

  it('shows the error the API returned and stays put', async () => {
    server.use(
      http.post(`${API}/auth/login`, () =>
        HttpResponse.json({ detail: 'Incorrect email address or password.' }, { status: 400 }),
      ),
    );

    renderLogin();
    await userEvent.type(await screen.findByLabelText(/email address/i), 'marta@example.org');
    await userEvent.type(screen.getByLabelText(/password/i), 'nope');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Incorrect email address or password.',
    );
    expect(screen.queryByRole('heading', { name: 'Dashboard' })).not.toBeInTheDocument();
  });

  it('puts a field error on its own input', async () => {
    server.use(
      http.post(`${API}/auth/login`, () =>
        HttpResponse.json({ email: ['Enter a valid email address.'] }, { status: 400 }),
      ),
    );

    renderLogin();
    await userEvent.type(await screen.findByLabelText(/email address/i), 'marta@example.org');
    await userEvent.type(screen.getByLabelText(/password/i), 'whatever');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    const input = await screen.findByLabelText(/email address/i);
    await waitFor(() => expect(input).toHaveAttribute('aria-invalid', 'true'));
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument();
  });

  it('refuses an address that is not one before asking the server', async () => {
    let asked = false;
    server.use(
      http.post(`${API}/auth/login`, () => {
        asked = true;
        return HttpResponse.json({ detail: 'nope' }, { status: 400 });
      }),
    );

    renderLogin();
    await userEvent.type(await screen.findByLabelText(/email address/i), 'bogus');
    await userEvent.type(screen.getByLabelText(/password/i), 'whatever');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(
      await screen.findByText('Use an email address like name@example.org.'),
    ).toBeInTheDocument();
    expect(asked).toBe(false);
  });

  it('drops everything the previous user had cached', async () => {
    const user = makeUser({ id: 2, email: 'marta@example.org' });
    server.use(http.post(`${API}/auth/login`, () => HttpResponse.json(user)));
    const client = persistentClient();
    client.setQueryData(['members', 'list'], [{ id: 1, name: 'Somebody else' }]);

    renderWithProviders(
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Dashboard />} />
      </Routes>,
      { route: '/login', client },
    );
    await userEvent.type(await screen.findByLabelText(/email address/i), 'marta@example.org');
    await userEvent.type(screen.getByLabelText(/password/i), 'correct-horse');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await screen.findByRole('heading', { name: 'Dashboard' });
    expect(client.getQueryData(['members', 'list'])).toBeUndefined();
  });

  it('seeds the auth cache with the user who just signed in', async () => {
    const user = makeUser({ id: 2, email: 'marta@example.org' });
    server.use(http.post(`${API}/auth/login`, () => HttpResponse.json(user)));
    const client = persistentClient();

    renderWithProviders(
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Dashboard />} />
      </Routes>,
      { route: '/login', client },
    );
    await userEvent.type(await screen.findByLabelText(/email address/i), 'marta@example.org');
    await userEvent.type(screen.getByLabelText(/password/i), 'correct-horse');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await screen.findByRole('heading', { name: 'Dashboard' });
    expect(client.getQueryData(AUTH_ME_KEY)).toEqual(user);
  });

  it('redirects a visitor who is already signed in', async () => {
    server.use(http.get(`${API}/auth/me`, () => HttpResponse.json(makeUser())));

    renderLogin('/login?next=%2Fprofile');

    expect(await screen.findByRole('heading', { name: 'My profile' })).toBeInTheDocument();
  });
});

describe('LoginPage layout', () => {
  it('puts the form in the auth card, with the button and the reset link as its actions', async () => {
    const { container } = renderLogin();

    const button = await screen.findByRole('button', { name: 'Sign in' });
    const actions = container.querySelector('.auth-card .auth__actions');
    expect(actions).toContainElement(button);
    expect(actions).toContainElement(screen.getByRole('link', { name: 'Forgot your password?' }));
  });

  it('offers the join link below the card', async () => {
    renderLogin();

    const join = await screen.findByRole('link', { name: 'Join CalDART' });
    expect(join.closest('.auth__footer')).not.toBeNull();
  });
});

describe('LoginPage reactivation', () => {
  async function signInToDeactivated() {
    await userEvent.type(await screen.findByLabelText(/email address/i), 'marta@example.org');
    await userEvent.type(screen.getByLabelText(/password/i), 'correct-horse');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  }

  it('offers reactivation to a deactivated account whose password matched', async () => {
    server.use(signInDeactivated());
    renderLogin();
    await signInToDeactivated();

    expect(
      await screen.findByText(
        'Reactivating brings back your roles and any membership that has not yet run out.',
      ),
    ).toBeInTheDocument();
  });

  it('shows the server sentence and never the bare code', async () => {
    server.use(signInDeactivated());
    renderLogin();
    await signInToDeactivated();

    expect(await screen.findByText(DEACTIVATED_LOGIN.detail)).toBeInTheDocument();
    expect(screen.queryByText('deactivated')).not.toBeInTheDocument();
  });

  it('posts the same credentials to reactivate and continues as a sign-in', async () => {
    let posted: unknown = null;
    server.use(
      signInDeactivated(),
      http.post(`${API}/auth/reactivate`, async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json(makeUser());
      }),
    );
    renderLogin('/login?next=%2Fprofile');
    await signInToDeactivated();
    await userEvent.click(await screen.findByRole('button', { name: 'Reactivate my account' }));

    await screen.findByRole('heading', { name: 'My profile' });
    expect(posted).toEqual({ email: 'marta@example.org', password: 'correct-horse' });
  });

  it('shows why a reactivation was refused', async () => {
    server.use(
      signInDeactivated(),
      http.post(`${API}/auth/reactivate`, () =>
        HttpResponse.json({ detail: 'Incorrect email address or password.' }, { status: 400 }),
      ),
    );
    renderLogin();
    await signInToDeactivated();
    await userEvent.click(await screen.findByRole('button', { name: 'Reactivate my account' }));

    expect(await screen.findByText('Incorrect email address or password.')).toBeInTheDocument();
  });

  it('offers no reactivation for an ordinary wrong password', async () => {
    server.use(
      http.post(`${API}/auth/login`, () =>
        HttpResponse.json({ detail: 'Incorrect email address or password.' }, { status: 400 }),
      ),
    );
    renderLogin();
    await signInToDeactivated();

    await screen.findByText('Incorrect email address or password.');
    expect(screen.queryByRole('button', { name: 'Reactivate my account' })).not.toBeInTheDocument();
  });
});
