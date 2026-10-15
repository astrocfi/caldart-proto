import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { RenewalScan } from '@/portal/api/types';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { RenewalsPanel, renewalRunSummary } from './RenewalsPanel';

const RESULT = {
  noticed: 2,
  warned: 0,
  charged: 1,
  failed: 0,
  paused: 0,
  skipped: 3,
  actions: [
    {
      kind: 'renewal_notice',
      member: 'Dana Lee',
      email: 'dana@example.org',
      on: '2026-06-19',
      amount_cents: null,
      detail: '',
    },
    {
      kind: 'charge',
      member: 'Marta Reyes',
      email: 'marta@example.org',
      on: '2026-06-19',
      amount_cents: 7000,
      detail: '',
    },
  ],
};

const STARTED: RenewalScan = {
  id: 7,
  started_at: '2026-06-19T13:31:00Z',
  finished_at: null,
  ok: false,
  error: '',
  result: null,
};

const FINISHED: RenewalScan = {
  ...STARTED,
  finished_at: '2026-06-19T13:32:00Z',
  ok: true,
  result: RESULT,
};

/**
 * A live run as the server takes it: the press answers 202 with the unfinished scan, and
 * each read of the scan answers the next of `reads`, the last one again once they run out.
 */
function liveRun(reads: RenewalScan[], bodies: unknown[] = []): void {
  let read = 0;
  server.use(
    http.post(`${API}/system/renewals/run`, async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json(STARTED, { status: 202 });
    }),
    http.get(`${API}/system/renewals/runs/7`, () => {
      const answer = reads[Math.min(read, reads.length - 1)];
      read += 1;
      return HttpResponse.json(answer);
    }),
  );
}

/** Clear the practice-run box, press Run now, and confirm the real charge. */
async function chargeForReal(): Promise<void> {
  await userEvent.click(
    screen.getByLabelText(
      'Practice run: show what would happen without charging anything (automatic renewal charges)',
    ),
  );
  await userEvent.click(screen.getByRole('button', { name: 'Run now: automatic renewal charges' }));
  await userEvent.click(screen.getByRole('button', { name: 'Charge what is due' }));
}

describe('renewalRunSummary', () => {
  it('says what a rehearsal would have done', () => {
    expect(renewalRunSummary(RESULT, true)).toBe(
      'Would notice 2, warn 0, charge 1, fail 0, pause 0, and skip 3.',
    );
  });

  it('says what a real run did', () => {
    expect(renewalRunSummary(RESULT, false)).toBe(
      'Noticed 2, warned 0, charged 1, failed 0, paused 0, and skipped 3.',
    );
  });
});

describe('RenewalsPanel', () => {
  it('rehearses by default and reports the counts', async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post(`${API}/system/renewals/run`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(RESULT);
      }),
    );
    renderWithProviders(<RenewalsPanel />);

    expect(
      screen.getByLabelText(
        'Practice run: show what would happen without charging anything (automatic renewal charges)',
      ),
    ).toBeChecked();
    await userEvent.click(
      screen.getByRole('button', { name: 'Run now: automatic renewal charges' }),
    );

    expect(
      await screen.findByText('Would notice 2, warn 0, charge 1, fail 0, pause 0, and skip 3.'),
    ).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: true }]);
  });

  it('lists who a rehearsal would write to, under a heading naming it a rehearsal', async () => {
    server.use(http.post(`${API}/system/renewals/run`, () => HttpResponse.json(RESULT)));
    renderWithProviders(<RenewalsPanel />);

    await userEvent.click(
      screen.getByRole('button', { name: 'Run now: automatic renewal charges' }),
    );

    expect(
      await screen.findByRole('heading', { name: 'What this run would do' }),
    ).toBeInTheDocument();
    const noticeRow = screen.getByRole('row', { name: /Dana Lee/ });
    expect(noticeRow).toHaveTextContent('Notice');
    const chargeRow = screen.getByRole('row', { name: /Marta Reyes/ });
    expect(chargeRow).toHaveTextContent('Charge');
    expect(chargeRow).toHaveTextContent('$70.00');
  });

  it("says that nothing was due when a rehearsal doesn't find any actions", async () => {
    server.use(
      http.post(`${API}/system/renewals/run`, () => HttpResponse.json({ ...RESULT, actions: [] })),
    );
    renderWithProviders(<RenewalsPanel />);

    await userEvent.click(
      screen.getByRole('button', { name: 'Run now: automatic renewal charges' }),
    );

    expect(await screen.findByText('Nothing was due')).toBeInTheDocument();
  });

  it('charges for real once the practice-run box is cleared', async () => {
    const bodies: unknown[] = [];
    liveRun([FINISHED], bodies);
    renderWithProviders(<RenewalsPanel />);

    await userEvent.click(
      screen.getByLabelText(
        'Practice run: show what would happen without charging anything (automatic renewal charges)',
      ),
    );
    await userEvent.click(
      screen.getByRole('button', { name: 'Run now: automatic renewal charges' }),
    );
    expect(bodies).toEqual([]);

    await userEvent.click(screen.getByRole('button', { name: 'Charge what is due' }));

    expect(
      await screen.findByText('Noticed 2, warned 0, charged 1, failed 0, paused 0, and skipped 3.'),
    ).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: false }]);
    expect(screen.getByRole('heading', { name: 'What this run did' })).toBeInTheDocument();
  });

  it('reads as running while the server takes the charges', async () => {
    liveRun([STARTED, FINISHED]);
    renderWithProviders(<RenewalsPanel />);

    await chargeForReal();

    expect(await screen.findByText(/^Running since/)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Run now: automatic renewal charges' }),
    ).toBeDisabled();
  });

  it('follows a running charge until it ends', async () => {
    liveRun([STARTED, FINISHED]);
    renderWithProviders(<RenewalsPanel />);

    await chargeForReal();

    expect(
      await screen.findByText(
        'Noticed 2, warned 0, charged 1, failed 0, paused 0, and skipped 3.',
        {},
        { timeout: 5_000 },
      ),
    ).toBeInTheDocument();
  });

  it('reports a charge run that stopped before it finished', async () => {
    liveRun([{ ...STARTED, finished_at: '2026-06-19T14:31:00Z', error: 'Did not finish.' }]);
    renderWithProviders(<RenewalsPanel />);

    await chargeForReal();

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The renewal run stopped: Did not finish.',
    );
  });

  it('moves the focus to the result after a real charge, not back to Run now', async () => {
    liveRun([FINISHED]);
    renderWithProviders(<RenewalsPanel />);

    await chargeForReal();

    const heading = await screen.findByRole('heading', { name: 'What this run did' });
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Cancel' })).toBeNull());
    expect(heading).toHaveFocus();
  });

  it("doesn't charge anything when the confirmation is waved off", async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post(`${API}/system/renewals/run`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json(RESULT);
      }),
    );
    renderWithProviders(<RenewalsPanel />);

    await userEvent.click(
      screen.getByLabelText(
        'Practice run: show what would happen without charging anything (automatic renewal charges)',
      ),
    );
    await userEvent.click(
      screen.getByRole('button', { name: 'Run now: automatic renewal charges' }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(bodies).toEqual([]);
    expect(
      screen.getByRole('button', { name: 'Run now: automatic renewal charges' }),
    ).toBeInTheDocument();
  });

  it('reports a run the server refused', async () => {
    server.use(
      http.post(`${API}/system/renewals/run`, () =>
        HttpResponse.json({ detail: 'Stripe is unreachable' }, { status: 502 }),
      ),
    );
    renderWithProviders(<RenewalsPanel />);

    await userEvent.click(
      screen.getByRole('button', { name: 'Run now: automatic renewal charges' }),
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('Stripe is unreachable');
  });
});
