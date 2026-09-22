import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import type { User } from '../../api/types';
import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { UserDetailPage } from './UserDetailPage';

const ROLES = [
  { slug: 'member', description: 'Own profile, own payments and membership.' },
  { slug: 'dart_leader', description: 'Look up any member before a flight.' },
  { slug: 'system_admin', description: 'Everything, plus backups and health.' },
];

const TARGET = makeUser({
  id: 7,
  email: 'priya@example.org',
  first_name: 'Priya',
  last_name: 'Raman',
  roles: ['member'],
});

interface StubOptions {
  target?: User;
  me?: User;
  patch?: Parameters<typeof http.patch>[1];
}

function stubDetail({ target = TARGET, me, patch }: StubOptions = {}) {
  const patched: unknown[] = [];
  server.use(
    signedInAs(me ?? makeUser({ id: 1, roles: ['member', 'user_admin'] })),
    http.get(`${API}/roles`, () => HttpResponse.json(ROLES)),
    http.get(`${API}/admin/users/${target.id}`, () => HttpResponse.json(target)),
    http.patch(
      `${API}/admin/users/${target.id}`,
      patch ??
        (async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          patched.push(body);
          return HttpResponse.json({ ...target, ...body });
        }),
    ),
  );
  return patched;
}

function renderDetail(id = String(TARGET.id)) {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/users/:id" element={<UserDetailPage />} />
    </Routes>,
    { route: `/admin/users/${id}` },
  );
}

describe('UserDetailPage', () => {
  it('shows the account and every role with its description', async () => {
    stubDetail();
    renderDetail();

    expect(await screen.findByRole('heading', { name: 'Priya Raman' })).toBeInTheDocument();
    expect(screen.getByLabelText(/first name/i)).toHaveValue('Priya');
    expect(screen.getByLabelText(/email address/i)).toHaveValue('priya@example.org');
    expect(screen.getByText('Look up any member before a flight.')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /member/i })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: /dart leader/i })).not.toBeChecked();
  });

  it('saves a role toggle', async () => {
    const patched = stubDetail();
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    await userEvent.click(screen.getByRole('checkbox', { name: /dart leader/i }));
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => expect(patched).toHaveLength(1));
    expect(patched[0]).toMatchObject({ roles: ['member', 'dart_leader'] });
    expect(await screen.findByText(/account saved/i)).toBeInTheDocument();
  });

  it('saves edited names and email', async () => {
    const patched = stubDetail();
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    await userEvent.clear(screen.getByLabelText(/first name/i));
    await userEvent.type(screen.getByLabelText(/first name/i), 'Priyanka');
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => expect(patched).toHaveLength(1));
    expect(patched[0]).toMatchObject({ first_name: 'Priyanka', email: 'priya@example.org' });
  });

  it('surfaces the escalation rule from the API', async () => {
    stubDetail({
      patch: () =>
        HttpResponse.json(
          {
            roles: ['Only a system administrator can grant or revoke the system_admin role.'],
          },
          { status: 400 },
        ),
    });
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    await userEvent.click(screen.getByRole('checkbox', { name: /system admin/i }));
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/only a system administrator/i);
  });

  it('will not let an admin deactivate their own account', async () => {
    const me = makeUser({ id: 7, roles: ['member', 'user_admin'] });
    stubDetail({ me });
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    expect(screen.getByRole('checkbox', { name: /active/i })).toBeDisabled();
    expect(screen.getByText(/cannot deactivate your own account/i)).toBeInTheDocument();
  });

  it('sends a password reset and reports what the API said', async () => {
    stubDetail();
    server.use(
      http.post(`${API}/admin/users/${TARGET.id}/send-password-reset`, () =>
        HttpResponse.json({ detail: 'Password reset email sent to priya@example.org.' }),
      ),
    );
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    await userEvent.click(screen.getByRole('button', { name: /send password reset/i }));

    expect(
      await screen.findByText('Password reset email sent to priya@example.org.'),
    ).toBeInTheDocument();
  });

  it('will not offer a reset for a deactivated account', async () => {
    stubDetail({ target: { ...TARGET, is_active: false } });
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    expect(screen.getByRole('button', { name: /send password reset/i })).toBeDisabled();
    expect(screen.getByText(/reactivate the account/i)).toBeInTheDocument();
  });

  it('explains a missing account rather than rendering an empty form', async () => {
    server.use(
      signedInAs(makeUser({ roles: ['member', 'user_admin'] })),
      http.get(`${API}/roles`, () => HttpResponse.json(ROLES)),
      http.get(`${API}/admin/users/404`, () =>
        HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
      ),
    );
    renderDetail('404');

    expect(await screen.findByText(/could not be loaded/i)).toBeInTheDocument();
  });
});
