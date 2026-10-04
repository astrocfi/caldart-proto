import { screen, waitFor } from '@testing-library/react';
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

/** Run now, once the bounce status has come back and the button is free to press. */
async function enabledRunNow(): Promise<HTMLElement> {
  const button = screen.getByRole('button', { name: 'Run now: bounce check' });
  await waitFor(() => expect(button).toBeEnabled());
  return button;
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

    await userEvent.click(await enabledRunNow());

    expect(
      await screen.findByText('Would mark 1 bounced, leave 1 unmatched, ignore 2, and skip 0.'),
    ).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: true }]);
  });

  it('runs for real once the practice-run box is cleared', async () => {
    const bodies = answerRuns(RESULT);
    renderWithProviders(<BouncesPanel />);

    await userEvent.click(
      screen.getByLabelText('Practice run: show what would happen, change nothing (bounce check)'),
    );
    await userEvent.click(await enabledRunNow());

    expect(
      await screen.findByText('Marked 1 bounced, left 1 unmatched, ignored 2, and skipped 0.'),
    ).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: false }]);
  });

  it('lists each bounce with who it reached and the report', async () => {
    answerRuns(RESULT);
    renderWithProviders(<BouncesPanel />);

    await userEvent.click(await enabledRunNow());

    const row = await screen.findByRole('row', { name: /Dana Doe/ });
    expect(row).toHaveTextContent('Bounced');
    expect(row).toHaveTextContent('5.1.1 550 User unknown');
  });

  it('lists an unmatched report by its address alone', async () => {
    answerRuns(RESULT);
    renderWithProviders(<BouncesPanel />);

    await userEvent.click(await enabledRunNow());

    const row = await screen.findByRole('row', { name: /stranger@example\.net/ });
    expect(row).toHaveTextContent('No matching email');
    expect(row).not.toHaveTextContent('·');
  });

  it('says so when no bounce mailbox is configured', async () => {
    answerRuns({ enabled: false, bounced: 0, unmatched: 0, ignored: 0, skipped: 0, actions: [] });
    renderWithProviders(<BouncesPanel />);

    await userEvent.click(await enabledRunNow());

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

    await userEvent.click(await enabledRunNow());

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not reach the bounce mailbox at imap.example.org',
    );
  });

  it('says bounce checking is off as the panel loads, and holds Run now back', async () => {
    server.use(http.get(`${API}/system/bounces`, () => HttpResponse.json({ enabled: false })));
    renderWithProviders(<BouncesPanel />);

    expect(await screen.findByText(BOUNCES_OFF)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run now: bounce check' })).toBeDisabled();
  });

  it('holds Run now back until the server has said whether checking is set up', async () => {
    let answer: (() => void) | undefined;
    server.use(
      http.get(`${API}/system/bounces`, async () => {
        await new Promise<void>((resolve) => {
          answer = resolve;
        });
        return HttpResponse.json({ enabled: true });
      }),
    );
    renderWithProviders(<BouncesPanel />);

    const button = screen.getByRole('button', { name: 'Run now: bounce check' });
    expect(button).toBeDisabled();
    await waitFor(() => expect(answer).toBeDefined());
    answer?.();
    await waitFor(() => expect(button).toBeEnabled());
  });

  it('asks the person who installed the site, in plain words', () => {
    expect(BOUNCES_OFF).toBe(
      'Bounce checking is off. Ask the person who installed the site to set up a bounce mailbox.',
    );
  });
});
