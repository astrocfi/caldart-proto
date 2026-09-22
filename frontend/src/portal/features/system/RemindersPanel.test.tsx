import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { Paginated, ReminderLogEntry } from '@/portal/api/types';
import { RemindersPanel, runSummary } from './RemindersPanel';

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

describe('runSummary', () => {
  it('says what a dry run would have done', () => {
    expect(runSummary({ sent: 3, skipped: 1 }, true)).toBe('Would send 3 emails, skipped 1.');
  });

  it('says what a real run did, in the singular', () => {
    expect(runSummary({ sent: 1, skipped: 0 }, false)).toBe('Sent 1 email, skipped 0.');
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
        return HttpResponse.json({ sent: 4, skipped: 2 });
      }),
    );
    renderWithProviders(<RemindersPanel />);
    await screen.findByText('Marta Reyes');

    expect(screen.getByLabelText('Dry run (send nothing)')).toBeChecked();
    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByText('Would send 4 emails, skipped 2.')).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: true }]);
  });

  it('sends for real once the dry-run box is cleared', async () => {
    const bodies: unknown[] = [];
    server.use(
      logHandler(ENTRIES),
      http.post(`${API}/system/reminders/run`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ sent: 1, skipped: 0 });
      }),
    );
    renderWithProviders(<RemindersPanel />);
    await screen.findByText('Marta Reyes');

    await userEvent.click(screen.getByLabelText('Dry run (send nothing)'));
    await userEvent.click(screen.getByRole('button', { name: 'Run now' }));

    expect(await screen.findByText('Sent 1 email, skipped 0.')).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: false }]);
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
