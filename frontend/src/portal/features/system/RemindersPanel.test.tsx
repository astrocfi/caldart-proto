import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { Paginated, ReminderLogEntry } from '@/portal/api/types';
import { RemindersPanel, runSummary, skippedBreakdown } from './RemindersPanel';

const ENTRIES: ReminderLogEntry[] = [
  {
    id: 2,
    user_id: 7,
    user_name: 'Marta Reyes',
    membership_id: 12,
    kind: 't30',
    sent_at: '2026-06-15T14:02:00Z',
    to_email: 'marta@example.org',
  },
];

function page(rows: ReminderLogEntry[]): Paginated<ReminderLogEntry> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

/** The log the panel shows under its run controls. */
function logHandler(rows: ReminderLogEntry[]) {
  return http.get(`${API}/admin/reminders/log`, () => HttpResponse.json(page(rows)));
}

const ACTIONS = [
  {
    kind: 't30' as const,
    member: 'Marta Reyes',
    email: 'marta@example.org',
    on: '2026-07-15',
    amount_cents: null,
    detail: '',
  },
];

describe('runSummary', () => {
  it('says what a dry run would have done', () => {
    expect(
      runSummary({ sent: 3, skipped: 1, failed: 0, skipped_by_reason: {}, actions: [] }, true),
    ).toBe('Would send 3 emails, skipped 1.');
  });

  it('says what a real run did, in the singular', () => {
    expect(
      runSummary({ sent: 1, skipped: 0, failed: 0, skipped_by_reason: {}, actions: [] }, false),
    ).toBe('Sent 1 email, skipped 0.');
  });
});

describe('skippedBreakdown', () => {
  it('lists every reason with a count above zero, in the order the guide gives them', () => {
    expect(skippedBreakdown({ already_sent: 10, auto_renew: 2 })).toBe(
      'Skipped: already sent 10, auto-renew on 2.',
    );
  });

  it('says nothing when every reason is at zero', () => {
    expect(skippedBreakdown({})).toBe('');
  });

  it('omits a reason present in the payload at zero', () => {
    expect(skippedBreakdown({ already_sent: 0, lifetime: 3 })).toBe('Skipped: lifetime member 3.');
  });
});

describe('RemindersPanel', () => {
  it('shows the reminder log under the run controls', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<RemindersPanel />);

    expect(await screen.findByText('Marta Reyes')).toBeInTheDocument();
  });

  it('runs a dry run by default and reports the result', async () => {
    const bodies: unknown[] = [];
    server.use(
      logHandler(ENTRIES),
      http.post(`${API}/system/reminders/run`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({
          sent: 4,
          skipped: 2,
          failed: 0,
          skipped_by_reason: {},
          actions: ACTIONS,
        });
      }),
    );
    renderWithProviders(<RemindersPanel />);
    await screen.findByText('Marta Reyes');

    expect(screen.getByLabelText('Dry run (send nothing)')).toBeChecked();
    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByText('Would send 4 emails, skipped 2.')).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: true }]);
    expect(screen.getByRole('heading', { name: 'What a live run would do' })).toBeInTheDocument();
    const actionsTable = screen.getByRole('table', { name: '1 action' });
    const row = within(actionsTable).getByRole('row', { name: /Marta Reyes/ });
    expect(row).toHaveTextContent('30 days before');
    expect(row).toHaveTextContent('2026/07/15');
  });

  it('says nothing was due when a run finds no actions', async () => {
    server.use(
      logHandler(ENTRIES),
      http.post(`${API}/system/reminders/run`, () =>
        HttpResponse.json({ sent: 0, skipped: 2, failed: 0, skipped_by_reason: {}, actions: [] }),
      ),
    );
    renderWithProviders(<RemindersPanel />);
    await screen.findByText('Marta Reyes');

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByText('Nothing was due')).toBeInTheDocument();
  });

  it('sends for real once the dry-run box is cleared', async () => {
    const bodies: unknown[] = [];
    server.use(
      logHandler(ENTRIES),
      http.post(`${API}/system/reminders/run`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({
          sent: 1,
          skipped: 0,
          failed: 0,
          skipped_by_reason: {},
          actions: [],
        });
      }),
    );
    renderWithProviders(<RemindersPanel />);
    await screen.findByText('Marta Reyes');

    await userEvent.click(screen.getByLabelText('Dry run (send nothing)'));
    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByText('Sent 1 email, skipped 0.')).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: false }]);
    expect(screen.getByRole('heading', { name: 'What this run did' })).toBeInTheDocument();
  });

  it('breaks the skip count down by reason', async () => {
    server.use(
      logHandler(ENTRIES),
      http.post(`${API}/system/reminders/run`, () =>
        HttpResponse.json({
          sent: 4,
          skipped: 12,
          failed: 0,
          skipped_by_reason: { already_sent: 10, auto_renew: 2 },
          actions: [],
        }),
      ),
    );
    renderWithProviders(<RemindersPanel />);
    await screen.findByText('Marta Reyes');

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(
      await screen.findByText('Skipped: already sent 10, auto-renew on 2.'),
    ).toBeInTheDocument();
  });

  it('reports the failed count only when it is above zero', async () => {
    server.use(
      logHandler(ENTRIES),
      http.post(`${API}/system/reminders/run`, () =>
        HttpResponse.json({
          sent: 4,
          skipped: 0,
          failed: 2,
          skipped_by_reason: {},
          actions: [],
        }),
      ),
    );
    renderWithProviders(<RemindersPanel />);
    await screen.findByText('Marta Reyes');

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByText('Failed 2.')).toBeInTheDocument();
  });

  it('shows neither breakdown line when nothing was skipped or failed', async () => {
    server.use(
      logHandler(ENTRIES),
      http.post(`${API}/system/reminders/run`, () =>
        HttpResponse.json({
          sent: 1,
          skipped: 0,
          failed: 0,
          skipped_by_reason: {},
          actions: [],
        }),
      ),
    );
    renderWithProviders(<RemindersPanel />);
    await screen.findByText('Marta Reyes');

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    await screen.findByText('Would send 1 email, skipped 0.');
    expect(screen.queryByText(/^Skipped:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Failed/)).not.toBeInTheDocument();
  });

  it('reports a failed run', async () => {
    server.use(
      logHandler(ENTRIES),
      http.post(`${API}/system/reminders/run`, () =>
        HttpResponse.json({ detail: 'SMTP refused the connection' }, { status: 500 }),
      ),
    );
    renderWithProviders(<RemindersPanel />);
    await screen.findByText('Marta Reyes');

    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('SMTP refused the connection');
  });
});
