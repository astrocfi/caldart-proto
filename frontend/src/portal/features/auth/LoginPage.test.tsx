import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { API, makeUser } from '../../../test/handlers';
import { renderWithProviders } from '../../../test/render';
import { server } from '../../../test/server';
import { LoginPage, safeNext } from './LoginPage';

function Dashboard() {
  return <h1>Dashboard</h1>;
}

function Profile() {
  return <h1>My profile</h1>;
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
    await userEvent.type(await screen.findByLabelText(/email address/i), 'bogus');
    await userEvent.type(screen.getByLabelText(/password/i), 'whatever');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    const input = await screen.findByLabelText(/email address/i);
    await waitFor(() => expect(input).toHaveAttribute('aria-invalid', 'true'));
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument();
  });

  it('redirects a visitor who is already signed in', async () => {
    server.use(http.get(`${API}/auth/me`, () => HttpResponse.json(makeUser())));

    renderLogin('/login?next=%2Fprofile');

    expect(await screen.findByRole('heading', { name: 'My profile' })).toBeInTheDocument();
  });
});
