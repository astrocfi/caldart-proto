import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { BulkEmailDetail, RoleSlug } from '@/portal/api/types';
import { makeBulkEmail } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderWithProviders, signedInClient } from '@test/render';
import { server } from '@test/server';
import { HIDDEN_MESSAGE, MessagesVisibility, SHOWN_MESSAGE } from './MessagesVisibility';

/**
 * Render the Messages line of a sent email for a person holding `roles`, answering
 * each hide or show with the email as asked; returns the bodies the server was sent.
 */
function renderLine(email: Partial<BulkEmailDetail> = {}, roles: RoleSlug[] = ['management']) {
  const sent = makeBulkEmail({ status: 'sent', started_at: '2026-04-06T17:00:00Z', ...email });
  const bodies: unknown[] = [];
  server.use(
    http.post(`${API}/bulk-email/${sent.id}/hide`, async ({ request }) => {
      const body = (await request.json()) as { hidden: boolean };
      bodies.push(body);
      return HttpResponse.json({ ...sent, hidden_from_archive: body.hidden });
    }),
  );
  renderWithProviders(<MessagesVisibility email={sent} />, { client: signedInClient(...roles) });
  return bodies;
}

describe('MessagesVisibility', () => {
  it('says everybody it went to can read it again', () => {
    renderLine();
    expect(screen.getByText(/^Everybody this email went to can read it again/)).toBeVisible();
  });

  it('hides the email from Messages after asking', async () => {
    const bodies = renderLine();
    await userEvent.click(screen.getByRole('button', { name: 'Hide from Email to me' }));
    const confirm = screen.getByRole('region', { name: 'Hide from Email to me' });
    await userEvent.click(within(confirm).getByRole('button', { name: 'Hide it' }));
    await waitFor(() => expect(bodies).toEqual([{ hidden: true }]));
  });

  it('says the email is hidden once it is', async () => {
    renderLine();
    await userEvent.click(screen.getByRole('button', { name: 'Hide from Email to me' }));
    await userEvent.click(screen.getByRole('button', { name: 'Hide it' }));
    expect(await screen.findByText(HIDDEN_MESSAGE)).toBeVisible();
  });

  it('shows a hidden email again at once', async () => {
    const bodies = renderLine({ hidden_from_archive: true });
    await userEvent.click(screen.getByRole('button', { name: 'Show in Email to me' }));
    await waitFor(() => expect(bodies).toEqual([{ hidden: false }]));
  });

  it('says a hidden email is back once shown', async () => {
    renderLine({ hidden_from_archive: true });
    await userEvent.click(screen.getByRole('button', { name: 'Show in Email to me' }));
    expect(await screen.findByText(SHOWN_MESSAGE)).toBeVisible();
  });

  it('says a hidden email keeps its history', () => {
    renderLine({ hidden_from_archive: true });
    expect(screen.getByText(/Its history here is unchanged\.$/)).toBeVisible();
  });

  it('offers nothing to a sender who is not CalDART management', () => {
    renderLine({}, ['dart_leader']);
    expect(screen.queryByRole('button', { name: 'Hide from Email to me' })).toBeNull();
  });
});
