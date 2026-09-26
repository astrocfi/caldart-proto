import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import {
  API,
  CURRENT_MEMBERSHIP,
  LIFETIME_MEMBERSHIP,
  NO_MEMBERSHIP,
  makeUser,
  signedInAs,
} from '@test/handlers';
import { makeTestQueryClient, renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { MembershipStatus } from '@/portal/api/types';
import { AUTH_ME_KEY } from '@/portal/auth/useAuth';
import { DeactivateCard } from './DeactivateCard';

function renderCard(membership: MembershipStatus = NO_MEMBERSHIP) {
  server.use(signedInAs(makeUser({ membership })));
  // Keep unobserved queries, so the cache can be read after the card has gone.
  const client = makeTestQueryClient();
  client.setDefaultOptions({
    queries: { retry: false, staleTime: 0, gcTime: Infinity },
    mutations: { retry: false },
  });
  return renderWithProviders(
    <Routes>
      <Route path="/profile" element={<DeactivateCard />} />
      <Route path="/login" element={<h1>Sign in</h1>} />
    </Routes>,
    { route: '/profile', client },
  );
}

async function deactivateWith(password: string) {
  await userEvent.type(await screen.findByLabelText(/current password/i), password);
  await userEvent.click(screen.getByRole('button', { name: 'Deactivate my account' }));
}

describe('<DeactivateCard/>', () => {
  beforeEach(() => {
    server.use(http.post(`${API}/auth/deactivate`, () => new HttpResponse(null, { status: 204 })));
  });

  it('says what deactivating keeps and how to come back', async () => {
    renderCard();
    expect(
      await screen.findByText(
        'You will be signed out and will not appear in any list. Your information and your ' +
          'payment history are kept. Sign in again any time to reactivate.',
      ),
    ).toBeInTheDocument();
  });

  it('names the date a current membership runs to', async () => {
    renderCard(CURRENT_MEMBERSHIP);
    expect(
      await screen.findByText(
        'Your membership is current through 2027/06/30. Deactivating ends it now; if you ' +
          'reactivate before that date, it resumes.',
      ),
    ).toBeInTheDocument();
  });

  it('tells a lifetime member the membership resumes', async () => {
    renderCard(LIFETIME_MEMBERSHIP);
    expect(
      await screen.findByText(
        'Your lifetime membership is current. Deactivating ends it now; if you reactivate, it ' +
          'resumes.',
      ),
    ).toBeInTheDocument();
  });

  it('says nothing about a membership there is none of', async () => {
    renderCard(NO_MEMBERSHIP);
    await screen.findByLabelText(/current password/i);
    expect(screen.queryByText(/Your membership is current/)).not.toBeInTheDocument();
  });

  it('keeps the button disabled until a password is typed', async () => {
    renderCard();
    await screen.findByLabelText(/current password/i);
    expect(screen.getByRole('button', { name: 'Deactivate my account' })).toBeDisabled();
  });

  it('posts the current password', async () => {
    let posted: unknown = null;
    server.use(
      http.post(`${API}/auth/deactivate`, async ({ request }) => {
        posted = await request.json();
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderCard();
    await deactivateWith('correct-horse');
    await screen.findByRole('heading', { name: 'Sign in' });
    expect(posted).toEqual({ current_password: 'correct-horse' });
  });

  it('goes to the sign-in page with a toast', async () => {
    renderCard();
    await deactivateWith('correct-horse');
    expect(
      await screen.findByText('Your account is deactivated. Sign in any time to reactivate it.'),
    ).toBeInTheDocument();
  });

  it('forgets who was signed in', async () => {
    const { client } = renderCard();
    await deactivateWith('correct-horse');
    await screen.findByRole('heading', { name: 'Sign in' });
    expect(client.getQueryData(AUTH_ME_KEY)).toBeNull();
  });

  it('shows a wrong password beside the field', async () => {
    server.use(
      http.post(`${API}/auth/deactivate`, () =>
        HttpResponse.json(
          { current_password: ['That is not your current password.'] },
          { status: 400 },
        ),
      ),
    );
    renderCard();
    await deactivateWith('wrong');
    expect(await screen.findByText('That is not your current password.')).toBeInTheDocument();
  });

  it('shows why a system administrator is refused', async () => {
    server.use(
      http.post(`${API}/auth/deactivate`, () =>
        HttpResponse.json(
          { detail: 'A system administrator cannot deactivate their own account.' },
          { status: 400 },
        ),
      ),
    );
    renderCard();
    await deactivateWith('correct-horse');
    expect(
      await screen.findByText('A system administrator cannot deactivate their own account.'),
    ).toBeInTheDocument();
  });
});
