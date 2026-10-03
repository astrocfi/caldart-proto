import { screen, within } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeSummary } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { BulkEmailSummary } from '@/portal/api/types';
import { SentPage } from './SentPage';

/** Answer the list with `rows`. */
function answerSent(rows: BulkEmailSummary[]): void {
  server.use(http.get(`${API}/bulk-email/sent`, () => HttpResponse.json(rows)));
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

  it('names the type of each send', async () => {
    answerSent([makeSummary({ status: 'sent', email_type_name: 'Mission' })]);
    renderWithProviders(<SentPage />);
    const row = (await screen.findByRole('link', { name: 'Hangar day' })).closest('tr');
    expect(within(row as HTMLElement).getByRole('cell', { name: 'Mission' })).toBeInTheDocument();
  });

  it('opens a send in progress to stop it there', async () => {
    answerSent([makeSummary({ status: 'sending' })]);
    renderWithProviders(<SentPage />);
    expect(await screen.findByRole('link', { name: 'Stop sending Hangar day' })).toHaveAttribute(
      'href',
      '/bulk-email/sent/7',
    );
  });

  it('opens a stopped send to send the rest there', async () => {
    answerSent([makeSummary({ status: 'stopped' })]);
    renderWithProviders(<SentPage />);
    expect(
      await screen.findByRole('link', { name: 'Send the rest of Hangar day' }),
    ).toHaveAttribute('href', '/bulk-email/sent/7');
  });

  it('offers Stop on an email waiting to send the rest', async () => {
    answerSent([makeSummary({ status: 'queued', started_at: '2026-04-06T17:00:00Z' })]);
    renderWithProviders(<SentPage />);
    expect(await screen.findByRole('link', { name: 'Stop sending Hangar day' })).toBeVisible();
  });

  it('offers each finished send results as a download', async () => {
    answerSent([makeSummary({ status: 'sent' })]);
    renderWithProviders(<SentPage />);
    const link = await screen.findByRole('link', { name: 'Download the results of Hangar day' });
    expect([link.textContent, link.getAttribute('href')]).toEqual([
      'Download results',
      '/api/v1/bulk-email/7/recipients.csv',
    ]);
  });

  it('puts the subject first, with a real width', async () => {
    answerSent([makeSummary({ status: 'sent' })]);
    renderWithProviders(<SentPage />);
    const table = await screen.findByRole('table');
    const first = within(table).getAllByRole('columnheader')[0];
    expect([first?.textContent, first?.className, table.style.minWidth.includes('16rem')]).toEqual([
      'Subject',
      'data-table__text',
      true,
    ]);
  });
});
