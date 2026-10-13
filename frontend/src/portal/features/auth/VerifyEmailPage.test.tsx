import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { User } from '@/portal/api/types';
import { AUTH_ME_KEY } from '@/portal/auth/useAuth';
import { VerifyEmailPage } from './VerifyEmailPage';

const LINK = '/verify-email?token=signed-token';
const INVALID = 'That verification link is invalid or has expired.';

/** Prints where the router ended up, so a navigation can be asserted on. */
function Where() {
  const location = useLocation();
  return <span data-testid="where">{`${location.pathname}${location.search}`}</span>;
}

function renderPage(route: string = LINK) {
  return renderWithProviders(
    <Routes>
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route path="*" element={<Where />} />
    </Routes>,
    { route },
  );
}

/** Answer the verify endpoint with success, recording the body it was sent. */
function verifySucceeds(): { posted: unknown[] } {
  const record: { posted: unknown[] } = { posted: [] };
  server.use(
    http.post(`${API}/auth/email/verify`, async ({ request }) => {
      record.posted.push(await request.json());
      return HttpResponse.json({ email: 'marta@example.org', changed: false });
    }),
  );
  return record;
}

describe('<VerifyEmailPage/>', () => {
  it('posts the token from the link', async () => {
    const record = verifySucceeds();
    renderPage();

    await screen.findByRole('heading', { name: 'Email verified' });
    expect(record.posted).toEqual([{ token: 'signed-token' }]);
  });

  it('says a link that moved the account names its new sign-in address', async () => {
    server.use(
      http.post(`${API}/auth/email/verify`, () =>
        HttpResponse.json({ email: 'marta.new@example.org', changed: true }),
      ),
    );
    renderPage();

    expect(
      await screen.findByText('marta.new@example.org is your sign-in address from now on.'),
    ).toBeInTheDocument();
  });

  it('titles a link that moved the account Email address changed', async () => {
    server.use(
      http.post(`${API}/auth/email/verify`, () =>
        HttpResponse.json({ email: 'marta.new@example.org', changed: true }),
      ),
    );
    renderPage();

    expect(
      await screen.findByRole('heading', { name: 'Email address changed' }),
    ).toBeInTheDocument();
  });

  it('says which address is verified', async () => {
    verifySucceeds();
    renderPage();

    expect(await screen.findByText('marta@example.org is verified.')).toBeInTheDocument();
  });

  it('continues to sign in, then the join wizard, when nobody is signed in', async () => {
    verifySucceeds();
    renderPage();

    expect(await screen.findByRole('link', { name: 'Continue' })).toHaveAttribute(
      'href',
      '/login?next=/join&email=marta%40example.org',
    );
  });

  it('continues to the join wizard when the profile is still incomplete', async () => {
    verifySucceeds();
    server.use(signedInAs(makeUser({ profile_complete: false })));
    renderPage();

    await userEvent.click(await screen.findByRole('link', { name: 'Continue' }));

    expect(await screen.findByTestId('where')).toHaveTextContent('/join');
  });

  it('continues to the join wizard when a member still owes their first dues', async () => {
    verifySucceeds();
    server.use(
      signedInAs(
        makeUser({
          membership: { status: 'none', expires_on: null, plan: null, is_lifetime: false },
        }),
      ),
    );
    renderPage();

    expect(await screen.findByRole('link', { name: 'Continue' })).toHaveAttribute('href', '/join');
  });

  it('continues to the dashboard when the member has finished joining', async () => {
    verifySucceeds();
    server.use(signedInAs(makeUser()));
    renderPage();

    expect(await screen.findByRole('link', { name: 'Continue' })).toHaveAttribute('href', '/');
  });

  it('asks who is signed in again when the first check crossed the verification', async () => {
    let isVerified = false;
    let releaseFirstCheck: () => void = () => undefined;
    const firstCheckHeld = new Promise<void>((settle) => {
      releaseFirstCheck = settle;
    });
    let checks = 0;
    server.use(
      http.get(`${API}/auth/me`, async () => {
        checks += 1;
        // The server read the account before the verification committed, so the
        // first answer is stale by the time it arrives.
        const snapshot = makeUser({ profile_complete: false, email_verified: isVerified });
        if (checks === 1) await firstCheckHeld;
        return HttpResponse.json(snapshot);
      }),
      http.post(`${API}/auth/email/verify`, () => {
        isVerified = true;
        releaseFirstCheck();
        return HttpResponse.json({ email: 'marta@example.org', changed: false });
      }),
    );
    const { client } = renderPage();

    await screen.findByRole('heading', { name: 'Email verified' });
    await waitFor(() =>
      expect(client.getQueryData<User | null>(AUTH_ME_KEY)?.email_verified).toBe(true),
    );
    expect(screen.getByRole('link', { name: 'Continue' })).toHaveAttribute('href', '/join');
  });

  it('shows the refusal and how to get a new link', async () => {
    server.use(
      http.post(`${API}/auth/email/verify`, () =>
        HttpResponse.json({ token: [INVALID] }, { status: 400 }),
      ),
    );
    renderPage();

    expect(await screen.findByText(INVALID)).toBeInTheDocument();
    expect(
      screen.getByText(
        /and press Resend verification message on the screen you land on to get a new one\./,
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login');
  });

  describe("a link that opens a donor's account", () => {
    const PROMPT = 'Choose a password to finish opening your account.';

    /**
     * Answer the verify endpoint as for a donor's link: a request for a password until
     * one comes, then `answer` for the body that carries it. Records every body posted.
     */
    function donorLink(
      answer: () => Response = () =>
        HttpResponse.json({ email: 'giver@example.org', changed: false }),
    ): { posted: unknown[] } {
      const record: { posted: unknown[] } = { posted: [] };
      server.use(
        http.post(`${API}/auth/email/verify`, async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          record.posted.push(body);
          if (body.password === undefined) {
            return HttpResponse.json(
              { password: [PROMPT], code: 'password_required' },
              { status: 400 },
            );
          }
          return answer();
        }),
      );
      return record;
    }

    async function choose(password: string, repeat: string = password): Promise<void> {
      await userEvent.type(await screen.findByLabelText(/^Password/), password);
      await userEvent.type(screen.getByLabelText(/^Repeat password/), repeat);
      await userEvent.click(screen.getByRole('button', { name: 'Open my account' }));
    }

    it('asks the person who followed it to choose a password', async () => {
      donorLink();
      renderPage();

      expect(
        await screen.findByRole('heading', { name: 'Choose your password' }),
      ).toBeInTheDocument();
    });

    it('shows no complaint before a password is chosen', async () => {
      donorLink();
      renderPage();

      await screen.findByRole('heading', { name: 'Choose your password' });
      expect(screen.queryByText(PROMPT)).not.toBeInTheDocument();
    });

    it('posts the token again with the chosen password', async () => {
      const record = donorLink();
      renderPage();

      await choose('Mailbox-Holder-Chooses-31');

      await screen.findByRole('heading', { name: 'Email verified' });
      expect(record.posted).toEqual([
        { token: 'signed-token' },
        { token: 'signed-token', password: 'Mailbox-Holder-Chooses-31' },
      ]);
    });

    it("shows the server's refusal of the password under the field", async () => {
      donorLink(() =>
        HttpResponse.json({ password: ['This password is too common.'] }, { status: 400 }),
      );
      renderPage();

      await choose('password');

      expect(await screen.findByText('This password is too common.')).toBeInTheDocument();
    });

    it('refuses two passwords that differ without asking the server', async () => {
      const record = donorLink();
      renderPage();

      await choose('Mailbox-Holder-Chooses-31', 'Something-Else-31');

      expect(await screen.findByText('The two passwords do not match.')).toBeInTheDocument();
      expect(record.posted).toHaveLength(1);
    });
  });

  it('refuses a link with no token without asking the server', async () => {
    let asked = false;
    server.use(
      http.post(`${API}/auth/email/verify`, () => {
        asked = true;
        return HttpResponse.json({ email: 'x@example.org', changed: false });
      }),
    );
    renderPage('/verify-email');

    expect(await screen.findByText(INVALID)).toBeInTheDocument();
    expect(asked).toBe(false);
  });
});
