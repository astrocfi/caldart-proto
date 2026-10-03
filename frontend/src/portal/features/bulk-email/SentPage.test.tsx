import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeSummary } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { BulkEmailSummary } from '@/portal/api/types';
import { SentPage } from './SentPage';

/** Answer the list with `rows`, recording each action posted. */
function answerSent(rows: BulkEmailSummary[]): string[] {
  const actions: string[] = [];
  server.use(
    http.get(`${API}/bulk-email/sent`, () => HttpResponse.json(rows)),
    http.post(`${API}/bulk-email/:id/:action`, ({ params }) => {
      actions.push(`${String(params.action)} ${String(params.id)}`);
      return HttpResponse.json(makeSummary({ id: Number(params.id) }));
    }),
  );
  return actions;
}

describe('SentPage', () => {
  it('lists each send with its counts', async () => {
    answerSent([
      makeSummary({
        status: 'sent',
        started_at: '2026-04-06T17:00:00Z',
        sent_count: 37,
        failed_count: 1,
        skipped_count: 4,
      }),
    ]);
    renderWithProviders(<SentPage />);
    const row = (await screen.findByRole('link', { name: 'Hangar day' })).closest('tr');
    expect(row).toHaveTextContent('Sent37');
  });

  it('stops a send in progress once confirmed', async () => {
    const actions = answerSent([makeSummary({ status: 'sending' })]);
    renderWithProviders(<SentPage />);
    await userEvent.click(await screen.findByRole('button', { name: 'Stop' }));
    await userEvent.click(screen.getByRole('button', { name: 'Stop now' }));
    await waitFor(() => expect(actions).toEqual(['stop 7']));
  });

  it('sends the rest of a stopped send once confirmed', async () => {
    const actions = answerSent([makeSummary({ status: 'stopped' })]);
    renderWithProviders(<SentPage />);
    await userEvent.click(await screen.findByRole('button', { name: 'Send the rest' }));
    await userEvent.click(screen.getByRole('button', { name: 'Send them now' }));
    await waitFor(() => expect(actions).toEqual(['resume 7']));
  });

  it('offers each send results as a download', async () => {
    answerSent([makeSummary({ status: 'sent' })]);
    renderWithProviders(<SentPage />);
    expect(
      await screen.findByRole('link', { name: 'Download the results of Hangar day' }),
    ).toHaveAttribute('href', '/api/v1/bulk-email/7/recipients.csv');
  });
});
