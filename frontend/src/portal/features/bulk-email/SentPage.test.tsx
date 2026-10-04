import { screen, within } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { answerSender, LEADER_SENDER, makeSummary, NO_DART_SENDER } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { headerWords, rowCells, tableHeaders } from '@test/table';
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

  it("opens a send's own page to duplicate it there", async () => {
    answerSent([makeSummary({ status: 'sent' })]);
    renderWithProviders(<SentPage />);
    const link = await screen.findByRole('link', { name: 'Duplicate Hangar day' });
    expect([link.textContent, link.getAttribute('href')]).toEqual([
      'Duplicate…',
      '/bulk-email/sent/7',
    ]);
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
    expect([
      first === undefined ? '' : headerWords(first),
      first?.classList.contains('data-table__identity'),
      table.style.minWidth.includes('9rem'),
    ]).toEqual(['Subject', true, true]);
  });

  it('shows CalDART management who wrote each email and its DART', async () => {
    answerSent([makeSummary({ status: 'sent', sender: 'Lane Lead', dart_name: 'Marin' })]);
    renderWithProviders(<SentPage />);
    const row = (await screen.findByRole('link', { name: 'Hangar day' })).closest('tr');
    const headers = tableHeaders(screen.getByRole('table'));
    const cells = rowCells(row as HTMLElement).map((cell) => cell.textContent);
    const at = headers.indexOf('From');
    expect([headers[at + 1], cells[at], cells[at + 1]]).toEqual(['DART', 'Lane Lead', 'Marin']);
  });

  it('leaves the From and DART columns out for a DART leader, whose emails are their own', async () => {
    answerSender(LEADER_SENDER);
    answerSent([makeSummary({ status: 'sent' })]);
    renderWithProviders(<SentPage />);
    await screen.findByRole('link', { name: 'Hangar day' });
    const headers = tableHeaders(screen.getByRole('table'));
    expect(headers.filter((header) => header === 'From' || header === 'DART')).toEqual([]);
  });

  it('puts the actions last, where every table keeps them', async () => {
    answerSent([makeSummary({ status: 'sent' })]);
    renderWithProviders(<SentPage />);
    const table = await screen.findByRole('table');
    expect(tableHeaders(table).at(-1)).toBe('Actions');
  });

  it('tells a DART leader with nothing sent where their emails will show', async () => {
    answerSender(LEADER_SENDER);
    answerSent([]);
    renderWithProviders(<SentPage />);
    expect(await screen.findByText('You have not sent an email yet')).toBeVisible();
    expect(screen.getByRole('link', { name: 'New email' })).toHaveAttribute(
      'href',
      '/bulk-email/compose',
    );
  });

  it('offers CalDART management a way to write one when nothing has been sent', async () => {
    answerSent([]);
    renderWithProviders(<SentPage />);
    expect(await screen.findByRole('link', { name: 'New email' })).toHaveAttribute(
      'href',
      '/bulk-email/compose',
    );
  });

  it('offers no way to write one to a DART leader who has nobody to send to', async () => {
    answerSender(NO_DART_SENDER);
    answerSent([]);
    renderWithProviders(<SentPage />);
    await screen.findByText('You have not sent an email yet');
    expect(screen.queryByRole('link', { name: 'New email' })).toBeNull();
  });

  it('tells a DART leader with no DART why, with the way to My profile', async () => {
    answerSender(NO_DART_SENDER);
    answerSent([]);
    renderWithProviders(<SentPage />);
    expect(await screen.findByRole('link', { name: 'Open My profile' })).toBeInTheDocument();
  });
});
