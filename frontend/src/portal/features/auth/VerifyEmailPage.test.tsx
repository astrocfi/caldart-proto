import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
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
      return HttpResponse.json({ email: 'marta@example.org' });
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

  it('says which address is verified', async () => {
    verifySucceeds();
    renderPage();

    expect(await screen.findByText('marta@example.org is verified.')).toBeInTheDocument();
  });

  it('continues to sign in when nobody is signed in', async () => {
    verifySucceeds();
    renderPage();

    expect(await screen.findByRole('link', { name: 'Continue' })).toHaveAttribute(
      'href',
      '/login?next=/',
    );
  });

  it('continues to the join wizard when the profile is still incomplete', async () => {
    verifySucceeds();
    server.use(signedInAs(makeUser({ profile_complete: false })));
    renderPage();

    await userEvent.click(await screen.findByRole('link', { name: 'Continue' }));

    expect(await screen.findByTestId('where')).toHaveTextContent('/join');
  });

  it('continues to the dashboard when the member has finished joining', async () => {
    verifySucceeds();
    server.use(signedInAs(makeUser()));
    renderPage();

    expect(await screen.findByRole('link', { name: 'Continue' })).toHaveAttribute('href', '/');
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
      screen.getByText(/and use Resend verification message on your dashboard to get a new one\./),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login');
  });

  it('refuses a link with no token without asking the server', async () => {
    let asked = false;
    server.use(
      http.post(`${API}/auth/email/verify`, () => {
        asked = true;
        return HttpResponse.json({ email: 'x@example.org' });
      }),
    );
    renderPage('/verify-email');

    expect(await screen.findByText(INVALID)).toBeInTheDocument();
    expect(asked).toBe(false);
  });
});
