import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { ChangeEmailPage } from './ChangeEmailPage';

/** Prints where the router ended up, so a navigation can be asserted on. */
function Where() {
  return <span data-testid="where">{useLocation().pathname}</span>;
}

function renderPage(route = '/change-email') {
  return renderWithProviders(
    <Routes>
      <Route path="/change-email" element={<ChangeEmailPage />} />
      <Route path="*" element={<Where />} />
    </Routes>,
    { route },
  );
}

async function submit(email: string, password: string) {
  await userEvent.type(await screen.findByLabelText(/^New email address/), email);
  await userEvent.type(screen.getByLabelText(/^Current password/), password);
  await userEvent.click(screen.getByRole('button', { name: 'Change email' }));
}

describe('<ChangeEmailPage/>', () => {
  beforeEach(() => {
    server.use(signedInAs(makeUser()));
  });

  it('names the address the account uses now', async () => {
    renderPage();

    expect(
      await screen.findByText(/Your sign-in address is member@example\.org\./),
    ).toBeInTheDocument();
  });

  it('says a waiting change keeps the current address', async () => {
    server.use(signedInAs(makeUser({ pending_email: 'new@example.org' })));
    renderPage();

    expect(
      await screen.findByText(
        'We sent a link to new@example.org. Your sign-in address stays member@example.org until you follow it.',
      ),
    ).toBeInTheDocument();
  });

  it('offers to send the link again while a change waits', async () => {
    server.use(signedInAs(makeUser({ pending_email: 'new@example.org' })));
    renderPage();

    expect(
      await screen.findByRole('button', { name: 'Resend verification message' }),
    ).toBeInTheDocument();
  });

  it("doesn't show a waiting change when there isn't one", async () => {
    renderPage();

    await screen.findByText(/Your sign-in address is member@example\.org\./);
    expect(screen.queryByRole('button', { name: 'Resend verification message' })).toBeNull();
  });

  it('sends the new address and the current password', async () => {
    let posted: unknown = null;
    server.use(
      http.post(`${API}/auth/email/change`, async ({ request }) => {
        posted = await request.json();
        return HttpResponse.json(makeUser({ pending_email: 'new@example.org' }));
      }),
    );
    renderPage();

    await submit('new@example.org', 'test-password-123');

    await screen.findByTestId('where');
    expect(posted).toEqual({ email: 'new@example.org', current_password: 'test-password-123' });
  });

  it('confirms with a toast and returns to the dashboard', async () => {
    server.use(
      http.post(`${API}/auth/email/change`, () =>
        HttpResponse.json(makeUser({ pending_email: 'new@example.org' })),
      ),
    );
    renderPage();

    await submit('new@example.org', 'test-password-123');

    expect(
      await screen.findByText(
        'We sent a link to new@example.org. Your sign-in address stays member@example.org until you follow it.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByTestId('where')).toHaveTextContent(/^\/$/);
  });

  it('returns to the page named by next', async () => {
    server.use(
      http.post(`${API}/auth/email/change`, () =>
        HttpResponse.json(makeUser({ pending_email: 'new@example.org' })),
      ),
    );
    renderPage('/change-email?next=/join');

    await submit('new@example.org', 'test-password-123');

    expect(await screen.findByTestId('where')).toHaveTextContent('/join');
  });

  it('ignores a next that leaves the portal', async () => {
    server.use(
      http.post(`${API}/auth/email/change`, () =>
        HttpResponse.json(makeUser({ pending_email: 'new@example.org' })),
      ),
    );
    renderPage('/change-email?next=//evil.example');

    await submit('new@example.org', 'test-password-123');

    expect(await screen.findByTestId('where')).toHaveTextContent(/^\/$/);
  });

  it('puts a wrong password on the password field', async () => {
    server.use(
      http.post(`${API}/auth/email/change`, () =>
        HttpResponse.json(
          { current_password: ['That is not your current password.'] },
          { status: 400 },
        ),
      ),
    );
    renderPage();

    await submit('new@example.org', 'wrong');

    expect(await screen.findByLabelText(/^Current password/)).toHaveAccessibleDescription(
      /That is not your current password\./,
    );
  });

  it('puts a taken address on the email field', async () => {
    server.use(
      http.post(`${API}/auth/email/change`, () =>
        HttpResponse.json(
          { email: ['Another account already uses that email address.'] },
          { status: 400 },
        ),
      ),
    );
    renderPage();

    await submit('taken@example.org', 'test-password-123');

    expect(await screen.findByLabelText(/^New email address/)).toHaveAccessibleDescription(
      /Another account already uses that email address\./,
    );
  });

  it('is a portal page under the Membership eyebrow, not a sign-in card', () => {
    const { container } = renderPage();

    expect(container.querySelector('.page__header .eyebrow')).toHaveTextContent('My account');
  });

  it('is titled as its menu entry is', () => {
    renderPage();

    expect(screen.getByRole('heading', { level: 1, name: 'Change email' })).toBeInTheDocument();
  });
});
