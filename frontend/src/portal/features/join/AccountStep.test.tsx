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

/** The answer `POST /auth/register` gives every address. */
function serveRegistration(): void {
  server.use(
    http.post(`${API}/auth/register`, () =>
      HttpResponse.json(
        { detail: 'We sent a message to marta@example.org. Follow the link in it to continue.' },
        { status: 202 },
      ),
    ),
  );
}

describe('<AccountStep/>', () => {
  it('shows Check your email once the server takes the registration', async () => {
    serveRegistration();
    renderWithProviders(<AccountStep onDone={() => {}} />);

    await fillAndSubmit();

    expect(await screen.findByRole('heading', { name: 'Check your email' })).toBeInTheDocument();
  });

  it('names the address the message went to', async () => {
    serveRegistration();
    renderWithProviders(<AccountStep onDone={() => {}} />);

    await fillAndSubmit();

    expect(
      await screen.findByText(
        'We sent a message to marta@example.org. Follow the link in it to continue.',
      ),
    ).toBeInTheDocument();
  });

  it('says the message tells an existing account how to sign in', async () => {
    serveRegistration();
    renderWithProviders(<AccountStep onDone={() => {}} />);

    await fillAndSubmit();

    expect(
      await screen.findByText(
        'If the address already has an account, the message says how to sign in instead.',
      ),
    ).toBeInTheDocument();
  });

  it('moves on to no other step, since nobody is signed in', async () => {
    serveRegistration();
    const handleDone = vi.fn();
    renderWithProviders(<AccountStep onDone={handleDone} />);

    await fillAndSubmit();

    await screen.findByRole('heading', { name: 'Check your email' });
    expect(handleDone).not.toHaveBeenCalled();
  });

  it('leaves the signed-in user unknown', async () => {
    serveRegistration();
    const { client } = renderWithProviders(<AccountStep onDone={() => {}} />);

    await fillAndSubmit();

    await screen.findByRole('heading', { name: 'Check your email' });
    expect(client.getQueryData(AUTH_ME_KEY)).toBeNull();
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
        return HttpResponse.json({ detail: 'We sent a message.' }, { status: 202 });
      }),
    );

    renderWithProviders(<AccountStep onDone={() => {}} />);
    await userEvent.click(await screen.findByRole('radio', { name: /Join as a friend/ }));
    await fillAndSubmit();

    await waitFor(() => expect(posted).toMatchObject({ kind: 'friend' }));
  });

  it('shows a refusal of the address beside the box', async () => {
    server.use(
      http.post(`${API}/auth/register`, () =>
        HttpResponse.json(
          { email: ['Enter an email address, such as name@example.org.'] },
          { status: 400 },
        ),
      ),
    );

    renderWithProviders(<AccountStep onDone={() => {}} />);
    await fillAndSubmit();

    expect(await screen.findByLabelText(/^Email address/)).toHaveAccessibleDescription(
      /Enter an email address, such as name@example.org\./,
    );
  });

  it('offers anybody with an account, friend or member, a way to sign in', async () => {
    renderWithProviders(<AccountStep onDone={() => {}} />);

    expect(
      await screen.findByRole('link', { name: 'Already have an account? Sign in' }),
    ).toHaveAttribute('href', '/login?next=%2Fportal%2Fjoin');
  });

  it('refuses an empty form before asking the server, and focuses its first box', async () => {
    const register = vi.fn();
    server.use(
      http.post(`${API}/auth/register`, () => {
        register();
        return HttpResponse.json({ detail: 'We sent a message.' }, { status: 202 });
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
      [
        'Enter your first name.',
        'Enter your last name.',
        'Enter your email address.',
        'Choose a password.',
      ].map((message) => screen.getByText(message).textContent),
    ).toEqual([
      'Enter your first name.',
      'Enter your last name.',
      'Enter your email address.',
      'Choose a password.',
    ]);
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
