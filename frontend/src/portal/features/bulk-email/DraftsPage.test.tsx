import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeSummary } from '@test/fixtures/bulkEmail';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { BulkEmailSummary } from '@/portal/api/types';
import { DraftsPage, NO_SUBJECT } from './DraftsPage';

/** Answer the list with `rows`, recording each delete and cancel. */
function answerDrafts(rows: BulkEmailSummary[]): { deleted: number[]; canceled: number[] } {
  const calls = { deleted: [] as number[], canceled: [] as number[] };
  server.use(
    http.get(`${API}/bulk-email/drafts`, () => HttpResponse.json(rows)),
    http.delete(`${API}/bulk-email/:id`, ({ params }) => {
      calls.deleted.push(Number(params.id));
      return new HttpResponse(null, { status: 204 });
    }),
    http.post(`${API}/bulk-email/:id/cancel`, ({ params }) => {
      calls.canceled.push(Number(params.id));
      return HttpResponse.json({});
    }),
  );
  return calls;
}

const SCHEDULED = makeSummary({
  id: 8,
  subject: 'Newsletter',
  status: 'queued',
  scheduled: true,
  start_at: '2027-04-07T15:00:00Z',
});

describe('DraftsPage', () => {
  it('lists each draft with its status in words', async () => {
    answerDrafts([makeSummary({ subject: '' }), SCHEDULED]);
    renderWithProviders(<DraftsPage />);
    const draft = (await screen.findByText(NO_SUBJECT)).closest('tr');
    expect(draft).toHaveTextContent('Draft');
    expect(screen.getByText('Newsletter').closest('tr')).toHaveTextContent('04/07/2027 at 8:00 AM');
  });

  it('opens a draft on its compose screen', async () => {
    answerDrafts([makeSummary()]);
    renderWithProviders(<DraftsPage />);
    expect(await screen.findByRole('link', { name: 'Hangar day' })).toHaveAttribute(
      'href',
      '/bulk-email/compose/7',
    );
  });

  it('cancels a scheduled email back to a draft', async () => {
    const calls = answerDrafts([SCHEDULED]);
    renderWithProviders(<DraftsPage />);
    await userEvent.click(
      await screen.findByRole('button', { name: 'Cancel the send of Newsletter' }),
    );
    await waitFor(() => expect(calls.canceled).toEqual([8]));
  });

  it('deletes a draft only once the trashcan is confirmed', async () => {
    const calls = answerDrafts([makeSummary()]);
    renderWithProviders(<DraftsPage />);
    await userEvent.click(
      await screen.findByRole('button', { name: 'Delete the draft Hangar day' }),
    );
    expect(calls.deleted).toEqual([]);
    const pair = screen.getByRole('group', { name: 'Delete the draft Hangar day' });
    await userEvent.click(within(pair).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(calls.deleted).toEqual([7]));
  });

  it('says so when there is no draft', async () => {
    answerDrafts([]);
    renderWithProviders(<DraftsPage />);
    expect(await screen.findByText('No drafts')).toBeVisible();
  });

  it('puts the subject first, with a real width', async () => {
    answerDrafts([makeSummary()]);
    renderWithProviders(<DraftsPage />);
    const table = await screen.findByRole('table');
    const first = within(table).getAllByRole('columnheader')[0];
    expect([first?.textContent, first?.className, table.style.minWidth.includes('16rem')]).toEqual([
      'Subject',
      'data-table__text',
      true,
    ]);
  });
});
