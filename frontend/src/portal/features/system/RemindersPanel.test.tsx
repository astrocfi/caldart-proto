import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '../../../test/handlers';
import { renderWithProviders } from '../../../test/render';
import { server } from '../../../test/server';
import type { Paginated, ReminderLogEntry } from '../../api/types';
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
  {
    id: 1,
    user_id: 8,
    user_name: 'Owen Delgado',
    membership_id: 13,
    kind: 'post30',
    sent_at: '2026-06-14T14:02:00Z',
    to_email: 'owen@example.org',
  },
];

function page(rows: ReminderLogEntry[]): Paginated<ReminderLogEntry> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

/** Log handler that honours the `kind` filter, like the API does. */
function logHandler(rows: ReminderLogEntry[], seen?: (kind: string | null) => void) {
  return http.get(`${API}/admin/reminders/log`, ({ request }) => {
    const kind = new URL(request.url).searchParams.get('kind');
    seen?.(kind);
    return HttpResponse.json(page(kind ? rows.filter((row) => row.kind === kind) : rows));
  });
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
  it('lists recent reminders', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<RemindersPanel />);

    expect(await screen.findByText('Marta Reyes')).toBeInTheDocument();
    // Scoped to the table: the kind filter uses the same labels.
    const table = within(screen.getByRole('table'));
    expect(table.getByText('30 days before')).toBeInTheDocument();
    expect(table.getByText('30 days after')).toBeInTheDocument();
    expect(table.getByText('marta@example.org')).toBeInTheDocument();
    expect(screen.getByText('2 reminders sent')).toBeInTheDocument();
  });

  it('shows an empty state when nothing has been sent', async () => {
    server.use(logHandler([]));
    renderWithProviders(<RemindersPanel />);

    expect(await screen.findByText('No reminders sent yet')).toBeInTheDocument();
  });

  it('filters the log by kind', async () => {
    const kinds: (string | null)[] = [];
    server.use(logHandler(ENTRIES, (kind) => kinds.push(kind)));
    renderWithProviders(<RemindersPanel />);
    await screen.findByText('Marta Reyes');

    await userEvent.selectOptions(screen.getByLabelText('Reminder'), 't30');

    await waitFor(() => expect(screen.queryByText('Owen Delgado')).not.toBeInTheDocument());
    expect(screen.getByText('Marta Reyes')).toBeInTheDocument();
    expect(kinds).toEqual([null, 't30']);
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
