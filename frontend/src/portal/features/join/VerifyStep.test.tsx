import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { API, makeUser } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { User } from '@/portal/api/types';
import { VerifyStep } from './VerifyStep';

const UNVERIFIED = makeUser({ email: 'new@example.org', email_verified: false });

/** Answer `/auth/me` with whatever `current()` returns at the time of the request. */
function stubMe(current: () => User) {
  server.use(http.get(`${API}/auth/me`, () => HttpResponse.json(current())));
}

describe('<VerifyStep/>', () => {
  it('asks the visitor to check their email, naming the address', async () => {
    stubMe(() => UNVERIFIED);
    renderWithProviders(<VerifyStep onDone={() => undefined} />);

    expect(await screen.findByRole('heading', { name: 'Check your email' })).toBeInTheDocument();
    expect(
      await screen.findByText(
        'We sent a verification message to new@example.org. Click the link in it to continue ' +
          'setting up your account.',
      ),
    ).toBeInTheDocument();
  });

  it('resends the message and says where it went', async () => {
    let resent = false;
    stubMe(() => UNVERIFIED);
    server.use(
      http.post(`${API}/auth/email/resend`, () => {
        resent = true;
        return HttpResponse.json(
          { detail: 'Verification message sent to new@example.org.' },
          { status: 202 },
        );
      }),
    );
    renderWithProviders(<VerifyStep onDone={() => undefined} />);

    await userEvent.click(await screen.findByRole('button', { name: 'Resend verification message' }));

    expect(await screen.findByText('Verification message sent to new@example.org.')).toBeVisible();
    expect(resent).toBe(true);
  });

  it('moves on once the server says the address is verified', async () => {
    let user = UNVERIFIED;
    stubMe(() => user);
    const handleDone = vi.fn();
    renderWithProviders(<VerifyStep onDone={handleDone} />);

    await screen.findByRole('heading', { name: 'Check your email' });
    user = { ...UNVERIFIED, email_verified: true };
    await userEvent.click(screen.getByRole('button', { name: "I've clicked the link" }));

    await vi.waitFor(() => expect(handleDone).toHaveBeenCalledTimes(1));
  });

  it('says so when the address is still unverified', async () => {
    stubMe(() => UNVERIFIED);
    const handleDone = vi.fn();
    renderWithProviders(<VerifyStep onDone={handleDone} />);

    await userEvent.click(await screen.findByRole('button', { name: "I've clicked the link" }));

    expect(
      await screen.findByText(
        'Not verified yet. Open the link in the message we sent, then try again.',
      ),
    ).toBeInTheDocument();
    expect(handleDone).not.toHaveBeenCalled();
  });

  it('offers a way to use a different address', async () => {
    stubMe(() => UNVERIFIED);
    renderWithProviders(<VerifyStep onDone={() => undefined} />);

    expect(
      await screen.findByRole('link', { name: 'Use a different email address' }),
    ).toHaveAttribute('href', '/change-email?next=/join');
  });
});
