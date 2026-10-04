import { screen } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { BulkEmailMessageDetail } from '@/portal/api/types';
import { EMAIL_FRAME_SANDBOX, emailDocument } from '@/portal/components/EmailFrame';
import { API } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import { MessagePage, NOT_AVAILABLE_MESSAGE } from './MessagePage';

const SPRING: BulkEmailMessageDetail = {
  id: 9,
  subject: 'Spring newsletter for Ann',
  sent_at: '2026-04-07T15:00:00Z',
  from_name: 'Grace Holloway',
  email_type_name: 'Operational',
  answer_url: '',
  html: '<html><body><p>Dear Ann,</p></body></html>',
  text: 'Dear Ann,',
};

/** Render `/messages/9` with the server answering `answer`. */
function renderMessage(answer: () => Response) {
  server.use(http.get(`${API}/messages/9`, answer));
  renderRoutes([{ path: '/messages/:id', element: <MessagePage /> }], { route: '/messages/9' });
}

describe('MessagePage', () => {
  it("shows the reader's own copy in a sandboxed frame", async () => {
    renderMessage(() => HttpResponse.json(SPRING));
    const frame = await screen.findByTitle('The email: Spring newsletter for Ann');
    expect([frame.getAttribute('sandbox'), frame.getAttribute('srcdoc')]).toEqual([
      EMAIL_FRAME_SANDBOX,
      emailDocument(SPRING.html),
    ]);
  });

  it('heads the page with the subject as the copy had it', async () => {
    renderMessage(() => HttpResponse.json(SPRING));
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Spring newsletter for Ann' }),
    ).toBeVisible();
  });

  it('says who sent it, when, and what kind of email it is', async () => {
    renderMessage(() => HttpResponse.json(SPRING));
    expect(
      await screen.findByText('From Grace Holloway on 04/07/2026, Operational email.'),
    ).toBeVisible();
  });

  it("says a message that is not the reader's is not available", async () => {
    renderMessage(() => HttpResponse.json({ detail: 'Not found.' }, { status: 404 }));
    expect(await screen.findByRole('alert')).toHaveTextContent(NOT_AVAILABLE_MESSAGE);
  });

  it('leads back to every message', async () => {
    renderMessage(() => HttpResponse.json(SPRING));
    expect(await screen.findByRole('link', { name: 'See all your messages' })).toHaveAttribute(
      'href',
      '/messages',
    );
  });
});
