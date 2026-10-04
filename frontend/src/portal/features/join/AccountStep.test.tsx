import { QueryClient } from '@tanstack/react-query';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { AUTH_ME_KEY } from '@/portal/auth/useAuth';
import { AccountStep } from './AccountStep';

async function fillAndSubmit(): Promise<void> {
  await userEvent.type(screen.getByLabelText(/^First name/), 'Marta');
  await userEvent.type(screen.getByLabelText(/^Last name/), 'Reyes');
  await userEvent.type(screen.getByLabelText(/^Email address/), 'marta@example.org');
  await userEvent.type(screen.getByLabelText(/^Password/), 'a-good-password');
  await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
}

/**
 * A client that keeps cached data alive without an observer, so that a query
 * seeded for the previous session can only disappear because registering
 * cleared it.  The shared test client collects such a query immediately
 * (`gcTime: 0`), which would let this test pass without the clear.
 */
function makeRetainingQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: Infinity },
      mutations: { retry: false },
    },
  });
}

describe('<AccountStep/>', () => {
  it('clears queries cached for a previous session and seeds the new user', async () => {
    const user = makeUser();
    server.use(http.post(`${API}/auth/register`, () => HttpResponse.json(user, { status: 201 })));

    const handleDone = vi.fn();
    const { client } = renderWithProviders(<AccountStep onDone={handleDone} />, {
      client: makeRetainingQueryClient(),
    });
    client.setQueryData(['members', 'roster'], ['someone else was here']);

    await fillAndSubmit();

    expect(handleDone).toHaveBeenCalled();
    expect(client.getQueryData(['members', 'roster'])).toBeUndefined();
    expect(client.getQueryData(AUTH_ME_KEY)).toEqual(user);
  });

  it('offers "Use a different account" as a button rather than a link', async () => {
    server.use(signedInAs(makeUser()));

    renderWithProviders(<AccountStep onDone={() => {}} />);

    expect(
      await screen.findByRole('button', { name: 'Use a different account' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Use a different account' })).not.toBeInTheDocument();
  });

  it('ends the session through the logout endpoint when it is pressed', async () => {
    let logouts = 0;
    server.use(
      signedInAs(makeUser()),
      http.post(`${API}/auth/logout`, () => {
        logouts += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithProviders(<AccountStep onDone={() => {}} />);
    await userEvent.click(await screen.findByRole('button', { name: 'Use a different account' }));

    await waitFor(() => expect(logouts).toBe(1));
  });

  it('offers the two kinds of account above the name fields, a member by default', async () => {
    renderWithProviders(<AccountStep onDone={() => {}} />);

    const member = await screen.findByRole('radio', { name: /Join as a member/ });
    const friend = screen.getByRole('radio', { name: /Join as a friend/ });
    expect(member).toBeChecked();
    expect(friend).not.toBeChecked();
    expect(
      member.compareDocumentPosition(screen.getByLabelText(/^First name/)) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it('describes each kind in the words the site uses', async () => {
    renderWithProviders(<AccountStep onDone={() => {}} />);

    expect(
      await screen.findByText('Pay yearly or lifetime dues and you are a member right away.'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('No dues. Support CalDART when you like, and become a member any time.'),
    ).toBeInTheDocument();
  });

  it('registers the kind that was chosen', async () => {
    let posted: Record<string, unknown> | null = null;
    server.use(
      http.post(`${API}/auth/register`, async ({ request }) => {
        posted = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeUser({ kind: 'friend' }), { status: 201 });
      }),
    );

    renderWithProviders(<AccountStep onDone={() => {}} />);
    await userEvent.click(await screen.findByRole('radio', { name: /Join as a friend/ }));
    await fillAndSubmit();

    await waitFor(() => expect(posted).toMatchObject({ kind: 'friend' }));
  });

  describe('when the address belongs to a donor', () => {
    function serveDonorUpgrade(): void {
      server.use(
        http.post(`${API}/auth/register`, () =>
          HttpResponse.json(
            { detail: 'Verification message sent to marta@example.org.' },
            { status: 202 },
          ),
        ),
      );
    }

    it('asks for the address to be verified without signing anybody in', async () => {
      serveDonorUpgrade();
      const handleDone = vi.fn();
      const { client } = renderWithProviders(<AccountStep onDone={handleDone} />, {
        client: makeRetainingQueryClient(),
      });

      await fillAndSubmit();

      expect(await screen.findByRole('heading', { name: 'Check your email' })).toBeInTheDocument();
      expect(
        screen.getByText(/We sent a verification message to marta@example.org\./),
      ).toBeInTheDocument();
      expect(handleDone).not.toHaveBeenCalled();
      expect(client.getQueryData(AUTH_ME_KEY)).toBeNull();
    });
  });

  it('offers a deactivated account the way back through the sign-in page', async () => {
    server.use(
      http.post(`${API}/auth/register`, () =>
        HttpResponse.json(
          {
            email: ['This email belongs to a deactivated account. Sign in to reactivate it.'],
            code: 'deactivated',
          },
          { status: 400 },
        ),
      ),
    );

    renderWithProviders(<AccountStep onDone={() => {}} />);
    await fillAndSubmit();

    expect(
      await screen.findByText(
        'This email belongs to a deactivated account. Sign in to reactivate it.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sign in to reactivate' })).toHaveAttribute(
      'href',
      '/login?email=marta%40example.org',
    );
  });

  it('offers no reactivation link for any other refusal', async () => {
    server.use(
      http.post(`${API}/auth/register`, () =>
        HttpResponse.json({ email: ['That address is already registered.'] }, { status: 400 }),
      ),
    );

    renderWithProviders(<AccountStep onDone={() => {}} />);
    await fillAndSubmit();

    await screen.findByText('That address is already registered.');
    expect(screen.queryByRole('link', { name: 'Sign in to reactivate' })).not.toBeInTheDocument();
  });

  it('offers anybody with an account, friend or member, a way to sign in', async () => {
    renderWithProviders(<AccountStep onDone={() => {}} />);

    expect(
      await screen.findByRole('link', { name: 'Already have an account? Sign in' }),
    ).toHaveAttribute('href', '/login?next=%2Fjoin');
  });

  it('refuses an empty form before asking the server, and focuses its first box', async () => {
    const register = vi.fn();
    server.use(
      http.post(`${API}/auth/register`, () => {
        register();
        return HttpResponse.json(makeUser(), { status: 201 });
      }),
    );
    renderWithProviders(<AccountStep onDone={() => {}} />);

    await userEvent.click(await screen.findByRole('button', { name: 'Create account' }));

    expect(screen.getByLabelText(/^First name/)).toHaveFocus();
    expect(register).not.toHaveBeenCalled();
  });

  it('says beside Create account how many boxes to check', async () => {
    renderWithProviders(<AccountStep onDone={() => {}} />);

    await userEvent.click(await screen.findByRole('button', { name: 'Create account' }));

    expect(await screen.findByText('Check the 4 highlighted fields.')).toBeInTheDocument();
  });

  it('names each empty box in the words the server uses', async () => {
    renderWithProviders(<AccountStep onDone={() => {}} />);

    await userEvent.click(await screen.findByRole('button', { name: 'Create account' }));

    expect(
      ['Enter your first name.', 'Enter your last name.', 'Choose a password.'].map(
        (message) => screen.getByText(message).textContent,
      ),
    ).toEqual(['Enter your first name.', 'Enter your last name.', 'Choose a password.']);
  });

  it('moves the focus to the box the server refused', async () => {
    server.use(
      http.post(`${API}/auth/register`, () =>
        HttpResponse.json({ password: ['This password is too common.'] }, { status: 400 }),
      ),
    );
    renderWithProviders(<AccountStep onDone={() => {}} />);

    await fillAndSubmit();

    await waitFor(() => expect(screen.getByLabelText(/^Password/)).toHaveFocus());
  });
});
