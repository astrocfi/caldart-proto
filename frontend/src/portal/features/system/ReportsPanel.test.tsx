import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { ReportRunResult, RunAction } from '@/portal/api/types';
import { ReportsPanel } from './ReportsPanel';

const ACTIONS: RunAction[] = [
  {
    kind: 'report',
    member: 'Ada Admin',
    email: 'ada@example.org',
    on: null,
    amount_cents: null,
    detail: 'Members, PDF',
  },
  {
    kind: 'roster',
    member: 'Lee Leader',
    email: 'lee@example.org',
    on: null,
    amount_cents: null,
    detail: 'Bay Area DART',
  },
];

function result(overrides: Partial<ReportRunResult> = {}): ReportRunResult {
  return { sent: 2, skipped: 0, failed: 0, skipped_by_reason: {}, actions: ACTIONS, ...overrides };
}

/** Answers the run with `answer`, recording each body the panel sends. */
function runHandler(answer: ReportRunResult, bodies: unknown[] = []) {
  return http.post(`${API}/system/reports/run`, async ({ request }) => {
    bodies.push(await request.json());
    return HttpResponse.json(answer);
  });
}

describe('ReportsPanel', () => {
  it('rehearses by default and says what a live run would send', async () => {
    const bodies: unknown[] = [];
    server.use(runHandler(result(), bodies));
    renderWithProviders(<ReportsPanel />);

    expect(screen.getByLabelText('Dry run (send nothing)')).toBeChecked();
    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByText('Would send 2 emails, skipped 0.')).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: true }]);
  });

  it('names each report and roster in the actions table', async () => {
    server.use(runHandler(result()));
    renderWithProviders(<ReportsPanel />);

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    const table = await screen.findByRole('table', { name: '2 actions' });
    expect(within(table).getByRole('row', { name: /Ada Admin/ })).toHaveTextContent(
      'ReportAda Admin · ada@example.orgMembers, PDF',
    );
    expect(within(table).getByRole('row', { name: /Lee Leader/ })).toHaveTextContent(
      'Bay Area DART',
    );
  });

  it('sends for real once the dry-run box is cleared', async () => {
    const bodies: unknown[] = [];
    server.use(runHandler(result({ sent: 1, actions: [] }), bodies));
    renderWithProviders(<ReportsPanel />);

    await userEvent.click(screen.getByLabelText('Dry run (send nothing)'));
    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByText('Sent 1 email, skipped 0.')).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: false }]);
  });

  it('breaks the skip count down by reason', async () => {
    server.use(
      runHandler(result({ skipped: 3, skipped_by_reason: { no_recipients: 2, no_email: 1 } })),
    );
    renderWithProviders(<ReportsPanel />);

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(
      await screen.findByText('Skipped: nobody ticked 2, no address on file 1.'),
    ).toBeInTheDocument();
  });

  it('reports the failed count when a send was refused', async () => {
    server.use(runHandler(result({ failed: 1 })));
    renderWithProviders(<ReportsPanel />);

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByText('Failed 1.')).toBeInTheDocument();
  });

  it("shows the server's refusal when the run fails", async () => {
    server.use(
      http.post(`${API}/system/reports/run`, () =>
        HttpResponse.json({ detail: 'The run failed.' }, { status: 500 }),
      ),
    );
    renderWithProviders(<ReportsPanel />);

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('The run failed.');
  });
});
