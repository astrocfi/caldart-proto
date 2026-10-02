import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import type { BounceRunResult } from '@/portal/api/types';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { BOUNCES_OFF, BouncesPanel, bounceRunSummary } from './BouncesPanel';

const RESULT: BounceRunResult = {
  enabled: true,
  bounced: 1,
  unmatched: 1,
  ignored: 2,
  skipped: 0,
  actions: [
    {
      kind: 'bounced',
      member: 'Dana Doe',
      email: 'gone@example.com',
      on: '2026-10-01',
      amount_cents: null,
      detail: '5.1.1 550 User unknown',
    },
    {
      kind: 'unmatched',
      member: '',
      email: 'stranger@example.net',
      on: null,
      amount_cents: null,
      detail: '5.1.10 Recipient not found',
    },
  ],
};

/** Answer every run with `body`, recording the request bodies in `bodies`. */
function answerRuns(body: BounceRunResult, bodies: unknown[] = []): unknown[] {
  server.use(
    http.post(`${API}/system/bounces/run`, async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json(body);
    }),
  );
  return bodies;
}

describe('bounceRunSummary', () => {
  it('says what a rehearsal would have done', () => {
    expect(bounceRunSummary(RESULT, true)).toBe(
      'Would mark 1 bounced, leave 1 unmatched, ignore 2, and skip 0.',
    );
  });

  it('says what a real run did', () => {
    expect(bounceRunSummary(RESULT, false)).toBe(
      'Marked 1 bounced, left 1 unmatched, ignored 2, and skipped 0.',
    );
  });
});

describe('BouncesPanel', () => {
  it('rehearses on the first press', async () => {
    const bodies = answerRuns(RESULT);
    renderWithProviders(<BouncesPanel />);

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(
      await screen.findByText('Would mark 1 bounced, leave 1 unmatched, ignore 2, and skip 0.'),
    ).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: true }]);
  });

  it('runs for real once the dry-run box is cleared', async () => {
    const bodies = answerRuns(RESULT);
    renderWithProviders(<BouncesPanel />);

    await userEvent.click(screen.getByLabelText('Dry run (change nothing)'));
    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(
      await screen.findByText('Marked 1 bounced, left 1 unmatched, ignored 2, and skipped 0.'),
    ).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: false }]);
  });

  it('lists each bounce with who it reached and the report', async () => {
    answerRuns(RESULT);
    renderWithProviders(<BouncesPanel />);

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    const row = await screen.findByRole('row', { name: /Dana Doe/ });
    expect(row).toHaveTextContent('Bounced');
    expect(row).toHaveTextContent('5.1.1 550 User unknown');
  });

  it('lists an unmatched report by its address alone', async () => {
    answerRuns(RESULT);
    renderWithProviders(<BouncesPanel />);

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    const row = await screen.findByRole('row', { name: /stranger@example\.net/ });
    expect(row).toHaveTextContent('No matching email');
    expect(row).not.toHaveTextContent('·');
  });

  it('says so when no bounce mailbox is configured', async () => {
    answerRuns({ enabled: false, bounced: 0, unmatched: 0, ignored: 0, skipped: 0, actions: [] });
    renderWithProviders(<BouncesPanel />);

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByText(BOUNCES_OFF)).toBeInTheDocument();
  });

  it('reports a mailbox the server could not read', async () => {
    server.use(
      http.post(`${API}/system/bounces/run`, () =>
        HttpResponse.json(
          { detail: 'Could not reach the bounce mailbox at imap.example.org: timed out' },
          { status: 400 },
        ),
      ),
    );
    renderWithProviders(<BouncesPanel />);

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not reach the bounce mailbox at imap.example.org',
    );
  });
});
