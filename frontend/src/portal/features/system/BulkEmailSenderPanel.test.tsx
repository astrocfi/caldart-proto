import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { BulkEmailRunResult } from '@/portal/api/types';
import { BulkEmailSenderPanel, SENDER_BUSY, senderRunSummary } from './BulkEmailSenderPanel';

const RESULT: BulkEmailRunResult = {
  busy: false,
  emails: 1,
  sent: 1,
  failed: 1,
  skipped: 2,
  out_of_time: false,
  remaining: 0,
  actions: [
    {
      kind: 'sent',
      member: 'Ann Able',
      email: 'ann@example.org',
      on: null,
      amount_cents: null,
      detail: 'Hangar day',
    },
    {
      kind: 'failed',
      member: 'Bea Bell',
      email: 'bea@example.org',
      on: null,
      amount_cents: null,
      detail: 'Refused by the mail server',
    },
  ],
};

/** Answer every run with `body`, counting the runs. */
function answerRuns(body: BulkEmailRunResult): { runs: number } {
  const calls = { runs: 0 };
  server.use(
    http.post(`${API}/system/bulk-email/run`, () => {
      calls.runs += 1;
      return HttpResponse.json(body);
    }),
  );
  return calls;
}

describe('senderRunSummary', () => {
  it('counts what the run did', () => {
    expect(senderRunSummary(RESULT)).toBe(
      'Worked on 1 bulk email: sent 1, failed 1, and skipped 2.',
    );
  });

  it('says a run that ran out of time leaves the rest to the server', () => {
    expect(senderRunSummary({ ...RESULT, out_of_time: true, remaining: 30 })).toContain(
      "30 copies are still to go, and the server's sender carries on with them within a minute.",
    );
  });
});

describe('BulkEmailSenderPanel', () => {
  it('runs the sender when Run now is pressed', async () => {
    const calls = answerRuns(RESULT);
    renderWithProviders(<BulkEmailSenderPanel />);
    await userEvent.click(screen.getByRole('button', { name: 'Run now: bulk email sender' }));
    expect(await screen.findByRole('status')).toHaveTextContent(senderRunSummary(RESULT));
    expect(calls.runs).toBe(1);
  });

  it('lists each copy the run tried with its result', async () => {
    answerRuns(RESULT);
    renderWithProviders(<BulkEmailSenderPanel />);
    await userEvent.click(screen.getByRole('button', { name: 'Run now: bulk email sender' }));
    const row = (await screen.findByText(/bea@example\.org/)).closest('tr');
    expect(row).toHaveTextContent('Failed');
  });

  it('keeps the button above what the run did', async () => {
    answerRuns(RESULT);
    renderWithProviders(<BulkEmailSenderPanel />);
    const button = screen.getByRole('button', { name: 'Run now: bulk email sender' });
    await userEvent.click(button);
    const table = await screen.findByRole('table');
    // The table follows the button in the page's order.
    expect(button.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('says so when another run was already sending', async () => {
    answerRuns({ ...RESULT, busy: true, emails: 0, sent: 0, failed: 0, skipped: 0, actions: [] });
    renderWithProviders(<BulkEmailSenderPanel />);
    await userEvent.click(screen.getByRole('button', { name: 'Run now: bulk email sender' }));
    expect(await screen.findByRole('status')).toHaveTextContent(SENDER_BUSY);
  });

  it('says only that nothing was due when nothing was waiting', async () => {
    answerRuns({ ...RESULT, emails: 0, sent: 0, failed: 0, skipped: 0, actions: [] });
    renderWithProviders(<BulkEmailSenderPanel />);
    await userEvent.click(screen.getByRole('button', { name: 'Run now: bulk email sender' }));
    expect(await screen.findByRole('status')).toHaveTextContent(/^Nothing was due\.$/);
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.queryByText(/Worked on/)).toBeNull();
  });

  it('names the job it describes', () => {
    renderWithProviders(<BulkEmailSenderPanel />);
    expect(screen.getByText(/^The bulk email sender runs every minute\./)).toBeInTheDocument();
  });
});
