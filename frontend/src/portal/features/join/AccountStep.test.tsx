import { QueryClient } from '@tanstack/react-query';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { API, makeUser } from '../../../test/handlers';
import { renderWithProviders } from '../../../test/render';
import { server } from '../../../test/server';
import { AUTH_ME_KEY } from '../../auth/useAuth';
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

    const onDone = vi.fn();
    const { client } = renderWithProviders(<AccountStep onDone={onDone} />, {
      client: makeRetainingQueryClient(),
    });
    client.setQueryData(['members', 'roster'], ['someone else was here']);

    await fillAndSubmit();

    expect(onDone).toHaveBeenCalled();
    expect(client.getQueryData(['members', 'roster'])).toBeUndefined();
    expect(client.getQueryData(AUTH_ME_KEY)).toEqual(user);
  });
});
