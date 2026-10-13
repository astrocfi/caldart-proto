import { QueryClient } from '@tanstack/react-query';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { API, makeUser } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { AUTH_ME_KEY } from '@/portal/auth/useAuth';
import { UndoEmailChangePage } from './UndoEmailChangePage';

const LINK = '/undo-email-change?token=signed-token';

function renderPage(route: string = LINK, client?: QueryClient) {
  return renderWithProviders(
    <Routes>
      <Route path="/undo-email-change" element={<UndoEmailChangePage />} />
    </Routes>,
    { route, client },
  );
}

/** Answer the undo endpoint with success, recording the bodies it was sent. */
function undoSucceeds(): { posted: unknown[] } {
  const record: { posted: unknown[] } = { posted: [] };
  server.use(
    http.post(`${API}/auth/email/undo`, async ({ request }) => {
      record.posted.push(await request.json());
      return HttpResponse.json({ email: 'marta@example.org', taken: false });
    }),
  );
  return record;
}

describe('<UndoEmailChangePage/>', () => {
  it('posts nothing until the visitor presses Undo the change', async () => {
    const record = undoSucceeds();
    renderPage();

    await screen.findByRole('button', { name: 'Undo the change' });
    expect(record.posted).toEqual([]);
  });

  it('posts the token from the link once', async () => {
    const record = undoSucceeds();
    renderPage();
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Undo the change' }));

    await screen.findByRole('heading', { name: 'Change undone' });
    expect(record.posted).toEqual([{ token: 'signed-token' }]);
  });

  it('says what undoing did to the account', async () => {
    undoSucceeds();
    renderPage();
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Undo the change' }));

    expect(
      await screen.findByText(
        'Your sign-in address is marta@example.org. Everybody has been signed out of the ' +
          'account, and its password no longer works. We sent marta@example.org a link to ' +
          'choose a new one.',
      ),
    ).toBeInTheDocument();
  });

  it('sends the visitor to sign in with the address filled in', async () => {
    undoSucceeds();
    renderPage();
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Undo the change' }));

    expect(await screen.findByRole('link', { name: 'Go to sign in' })).toHaveAttribute(
      'href',
      '/login?email=marta%40example.org',
    );
  });

  it('forgets whoever was signed in, since every session has ended', async () => {
    undoSucceeds();
    // A client that keeps data without an observer, so only the undo can empty it.
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } },
    });
    client.setQueryData(AUTH_ME_KEY, makeUser());
    renderPage(LINK, client);
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Undo the change' }));

    await screen.findByRole('heading', { name: 'Change undone' });
    expect(client.getQueryData(AUTH_ME_KEY)).toBeNull();
  });

  it('shows the reason the server refused the link', async () => {
    server.use(
      http.post(`${API}/auth/email/undo`, () =>
        HttpResponse.json(
          { token: ['That link is invalid, has expired, or has been used.'] },
          { status: 400 },
        ),
      ),
    );
    renderPage();
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Undo the change' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'That link is invalid, has expired, or has been used.',
    );
  });

  it('titles a refused link Change not undone', async () => {
    server.use(
      http.post(`${API}/auth/email/undo`, () =>
        HttpResponse.json(
          { token: ['Another account uses your previous address.'] },
          { status: 400 },
        ),
      ),
    );
    renderPage();
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Undo the change' }));

    expect(await screen.findByRole('heading', { name: 'Change not undone' })).toBeInTheDocument();
  });

  it('offers the forgot-password page when the link fails', async () => {
    server.use(
      http.post(`${API}/auth/email/undo`, () =>
        HttpResponse.json({ token: ['That link is invalid.'] }, { status: 400 }),
      ),
    );
    renderPage();
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Undo the change' }));

    expect(await screen.findByRole('link', { name: 'Forgot your password?' })).toHaveAttribute(
      'href',
      '/forgot-password',
    );
  });

  it('says the account was closed when the previous address is taken', async () => {
    server.use(
      http.post(`${API}/auth/email/undo`, () =>
        HttpResponse.json({ email: 'moved@example.org', taken: true }),
      ),
    );
    renderPage();
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Undo the change' }));

    expect(await screen.findByRole('heading', { name: 'Account closed' })).toBeInTheDocument();
  });

  it('refuses a link with no token without asking the server', () => {
    const record = undoSucceeds();
    renderPage('/undo-email-change');

    expect(screen.getByRole('alert')).toHaveTextContent(
      'That link is invalid, has expired, or has been used.',
    );
    expect(record.posted).toEqual([]);
  });
});
