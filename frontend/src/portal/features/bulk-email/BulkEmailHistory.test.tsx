import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { BulkEmail, BulkEmailDetail } from '@/portal/api/types';
import { BulkEmailHistory } from './BulkEmailHistory';

const SEND: BulkEmail = {
  id: 7,
  subject: 'Spring seminar',
  body: 'Join us.',
  filters: { kind: 'friend' },
  sender: 'Grace Holloway',
  created_at: '2026-10-02T17:00:00Z',
  sent_at: '2026-10-02T17:00:05Z',
  sent_count: 12,
  failed_count: 1,
  skipped_count: 2,
};

const DETAIL: BulkEmailDetail = {
  ...SEND,
  recipients: [
    { user_id: 1, name: 'Ann Able', email: 'ann@example.org', status: 'sent', reason: '' },
  ],
};

/** Answer the history with one send, and its results. */
function answerHistory(history: BulkEmail[] = [SEND]): void {
  server.use(
    http.get(`${API}/bulk-email`, () => HttpResponse.json(history)),
    http.get(`${API}/bulk-email/7`, () => HttpResponse.json(DETAIL)),
  );
}

describe('BulkEmailHistory', () => {
  it('lists each send on one line, dated, with its sender and counts', async () => {
    answerHistory();
    renderWithProviders(<BulkEmailHistory />);

    const table = await screen.findByRole('table', { name: '1 bulk email sent' });
    expect(within(table).getByRole('row', { name: /Spring seminar/ })).toHaveTextContent(
      '10/02/2026Spring seminarGrace Holloway1212',
    );
  });

  it('downloads a send’s list as a CSV', async () => {
    answerHistory();
    renderWithProviders(<BulkEmailHistory />);

    expect(
      await screen.findByRole('link', { name: 'Download the list of Spring seminar' }),
    ).toHaveAttribute('href', '/api/v1/bulk-email/7/recipients.csv');
  });

  it('opens a send’s results', async () => {
    answerHistory();
    const user = userEvent.setup();
    renderWithProviders(<BulkEmailHistory />);

    await user.click(await screen.findByRole('button', { name: 'Results of Spring seminar' }));

    const results = await screen.findByRole('region', { name: 'Results of Spring seminar' });
    expect(within(results).getByRole('row', { name: /Ann Able/ })).toHaveTextContent(
      'SentAnn Able · ann@example.org',
    );
  });

  it('says so when nothing has been sent', async () => {
    answerHistory([]);
    renderWithProviders(<BulkEmailHistory />);

    expect(await screen.findByText('No bulk email has been sent')).toBeInTheDocument();
  });

  it('marks a send that stopped part way as interrupted', async () => {
    answerHistory([{ ...SEND, sent_at: null }]);
    renderWithProviders(<BulkEmailHistory />);

    const table = await screen.findByRole('table', { name: '1 bulk email sent' });
    expect(within(table).getByRole('row', { name: /Spring seminar/ })).toHaveTextContent(
      '10/02/2026 InterruptedSpring seminar',
    );
  });
});
