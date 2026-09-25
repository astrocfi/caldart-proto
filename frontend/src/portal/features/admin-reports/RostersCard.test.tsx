import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API, subscriptionHandlers } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { ReportRunResult, Roster } from '@/portal/api/types';
import { RostersCard } from './RostersCard';

const ROSTERS: Roster[] = [
  {
    dart_id: 3,
    name: 'Bay Area DART',
    roster_recipients: 2,
    roster_sent_at: '2026-09-15T18:00:00Z',
  },
  { dart_id: 4, name: 'Sierra DART', roster_recipients: 0, roster_sent_at: null },
];

const RUN: ReportRunResult = {
  sent: 2,
  skipped: 1,
  failed: 0,
  skipped_by_reason: { no_recipients: 1 },
  actions: [
    {
      kind: 'roster',
      member: 'Lee Leader',
      email: 'lee@example.org',
      on: null,
      amount_cents: null,
      detail: 'Bay Area DART',
    },
  ],
};

/** Render the card over the two rosters; every send body lands in `bodies`. */
async function renderCard(bodies: unknown[] = []) {
  server.use(
    ...subscriptionHandlers({ rosters: ROSTERS }),
    http.post(`${API}/reports/rosters/send`, async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json(RUN);
    }),
  );
  renderWithProviders(<RostersCard />);
  return screen.findByRole('table', { name: '2 DARTs' });
}

describe('RostersCard', () => {
  it("counts each DART's recipients and dates its last roster", async () => {
    const table = await renderCard();

    expect(within(table).getByRole('row', { name: /Bay Area DART/ })).toHaveTextContent(
      'Bay Area DART22026/09/15',
    );
    expect(within(table).getByRole('row', { name: /Sierra DART/ })).toHaveTextContent(
      'Sierra DART0—',
    );
  });

  it('rehearses by default and names who would receive a roster', async () => {
    const bodies: unknown[] = [];
    await renderCard(bodies);

    expect(screen.getByLabelText('Dry run (send nothing)')).toBeChecked();
    await userEvent.click(screen.getByRole('button', { name: 'Send rosters now' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Would send 2 emails, skipped 1.');
    expect(bodies).toEqual([{ dry_run: true }]);
    const actions = screen.getByRole('table', { name: '1 action' });
    expect(within(actions).getByRole('row', { name: /Lee Leader/ })).toHaveTextContent(
      'Bay Area DART',
    );
    expect(screen.getByText('Skipped: nobody ticked 1.')).toBeInTheDocument();
  });

  it('sends for real once the dry-run box is cleared', async () => {
    const bodies: unknown[] = [];
    await renderCard(bodies);

    await userEvent.click(screen.getByLabelText('Dry run (send nothing)'));
    await userEvent.click(screen.getByRole('button', { name: 'Send rosters now' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Sent 2 emails, skipped 1.');
    expect(bodies).toEqual([{ dry_run: false }]);
  });
});
