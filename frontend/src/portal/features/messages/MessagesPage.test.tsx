import { screen, within } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { BulkEmailMessage } from '@/portal/api/types';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { MessagesPage } from './MessagesPage';

const SPRING: BulkEmailMessage = {
  id: 9,
  subject: 'Spring newsletter for Ann',
  sent_at: '2026-04-07T15:00:00Z',
  from_name: 'Grace Holloway',
  email_type_name: 'Operational',
  answer_url: '',
};

/** Render the list with `/messages` answering `rows`. */
function renderList(rows: BulkEmailMessage[]) {
  server.use(http.get(`${API}/messages`, () => HttpResponse.json(rows)));
  renderWithProviders(<MessagesPage />, { route: '/messages' });
}

describe('MessagesPage', () => {
  it("opens a mission callout on the reader's own answer page", async () => {
    const answerUrl = 'https://caldart.example.org/mail/callout/abc123';
    renderList([{ ...SPRING, subject: 'Fire near Paradise', answer_url: answerUrl }]);
    const link = await screen.findByRole('link', { name: 'Fire near Paradise' });
    expect(link).toHaveAttribute('href', answerUrl);
  });

  it('speaks to the reader of their own email, not of bulk email', () => {
    renderList([SPRING]);
    expect(screen.getByText('Your email')).toBeVisible();
  });

  it('lists each message with its date, subject, sender, and kind', async () => {
    renderList([SPRING]);
    const row = (await screen.findByRole('link', { name: SPRING.subject })).closest('tr');
    expect(row).toHaveTextContent('04/07/2026Spring newsletter for AnnGrace HollowayOperational');
  });

  it('opens a message from its subject', async () => {
    renderList([SPRING]);
    expect(await screen.findByRole('link', { name: SPRING.subject })).toHaveAttribute(
      'href',
      '/messages/9',
    );
  });

  it('keeps the newest first, as the server sends them', async () => {
    renderList([SPRING, { ...SPRING, id: 8, subject: 'March meeting' }]);
    const table = await screen.findByRole('table', { name: '2 messages' });
    expect(
      within(table)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(['Spring newsletter for Ann', 'March meeting']);
  });

  it('says so when there are no messages yet', async () => {
    renderList([]);
    expect(await screen.findByText('No messages yet')).toBeVisible();
  });

  it('says mail about the account itself is not listed', async () => {
    renderList([]);
    expect(await screen.findByText(/^Email about your own account/)).toBeVisible();
  });

  it('says so when the list cannot be loaded', async () => {
    server.use(http.get(`${API}/messages`, () => new HttpResponse(null, { status: 500 })));
    renderWithProviders(<MessagesPage />, { route: '/messages' });
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded');
  });
});
