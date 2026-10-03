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
});

describe('BulkEmailSenderPanel', () => {
  it('runs the sender when Run now is pressed', async () => {
    const calls = answerRuns(RESULT);
    renderWithProviders(<BulkEmailSenderPanel />);
    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));
    expect(await screen.findByRole('status')).toHaveTextContent(senderRunSummary(RESULT));
    expect(calls.runs).toBe(1);
  });

  it('lists each copy the run tried with its result', async () => {
    answerRuns(RESULT);
    renderWithProviders(<BulkEmailSenderPanel />);
    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));
    const row = (await screen.findByText(/bea@example\.org/)).closest('tr');
    expect(row).toHaveTextContent('Failed');
  });

  it('says so when another run was already sending', async () => {
    answerRuns({ ...RESULT, busy: true, emails: 0, sent: 0, failed: 0, skipped: 0, actions: [] });
    renderWithProviders(<BulkEmailSenderPanel />);
    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));
    expect(await screen.findByRole('status')).toHaveTextContent(SENDER_BUSY);
  });
});
