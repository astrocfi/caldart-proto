import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { Paginated, ReminderLogEntry } from '@/portal/api/types';
import { makeReminderSchedule } from '@test/fixtures/reminders';
import { ReminderLog } from './ReminderLog';

const ENTRIES: ReminderLogEntry[] = [
  {
    id: 2,
    user_id: 7,
    user_name: 'Marta Reyes',
    membership_id: 12,
    kind: 'second',
    sent_at: '2026-06-15T14:02:00Z',
    to_email: 'marta@example.org',
  },
  {
    id: 1,
    user_id: 8,
    user_name: 'Owen Delgado',
    membership_id: 13,
    kind: 'lapsed',
    sent_at: '2026-06-14T14:02:00Z',
    to_email: 'owen@example.org',
  },
];

function page(rows: ReminderLogEntry[]): Paginated<ReminderLogEntry> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

/** Log handler that honors the `kind` filter, like the API does. */
function logHandler(rows: ReminderLogEntry[], seen?: (kind: string | null) => void) {
  return http.get(`${API}/admin/reminders/log`, ({ request }) => {
    const kind = new URL(request.url).searchParams.get('kind');
    seen?.(kind);
    return HttpResponse.json(page(kind ? rows.filter((row) => row.kind === kind) : rows));
  });
}

describe('ReminderLog', () => {
  it('lists recent reminders', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<ReminderLog />);

    expect(await screen.findByText('Marta Reyes')).toBeInTheDocument();
    // Scoped to the table: the kind filter uses the same labels.
    const table = within(screen.getByRole('table'));
    expect(await table.findByText('30 days before')).toBeInTheDocument();
    expect(table.getByText('30 days after')).toBeInTheDocument();
    expect(table.getByText('marta@example.org')).toBeInTheDocument();
  });

  it('names each kind by the days of the stored schedule', async () => {
    server.use(
      logHandler(ENTRIES),
      http.get(`${API}/admin/reminders/schedule`, () =>
        HttpResponse.json(makeReminderSchedule({ second_days_before: 20, lapsed_days_after: 14 })),
      ),
    );
    renderWithProviders(<ReminderLog />);

    const table = within(await screen.findByRole('table'));
    expect(await table.findByText('20 days before')).toBeInTheDocument();
    expect(table.getByText('14 days after')).toBeInTheDocument();
  });

  it('captions the table with how many have been sent', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<ReminderLog />);

    expect(await screen.findByText('2 reminders sent')).toBeInTheDocument();
  });

  it('shows an empty state when nothing has been sent', async () => {
    server.use(logHandler([]));
    renderWithProviders(<ReminderLog />);

    expect(await screen.findByText('No reminders sent yet')).toBeInTheDocument();
  });

  it('filters the log by kind', async () => {
    const kinds: (string | null)[] = [];
    server.use(logHandler(ENTRIES, (kind) => kinds.push(kind)));
    renderWithProviders(<ReminderLog />);
    await screen.findByText('Marta Reyes');

    await userEvent.selectOptions(screen.getByLabelText('Reminder'), 'second');

    await waitFor(() => expect(screen.queryByText('Owen Delgado')).not.toBeInTheDocument());
    expect(screen.getByText('Marta Reyes')).toBeInTheDocument();
    expect(kinds).toEqual([null, 'second']);
  });

  it('offers every kind plus "Any kind" in the filter', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<ReminderLog />);
    await screen.findByText('Marta Reyes');
    await within(screen.getByRole('table')).findByText('30 days before');

    const options = within(screen.getByLabelText('Reminder')).getAllByRole('option');
    expect(options.map((option) => option.textContent)).toEqual([
      'Any kind',
      '60 days before',
      '30 days before',
      '7 days before',
      'Expired',
      '30 days after',
    ]);
  });

  it('carries no controls for running the scan', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<ReminderLog />);
    await screen.findByText('Marta Reyes');

    expect(screen.queryByRole('button', { name: 'Run now' })).not.toBeInTheDocument();
  });

  it('offers to reset the filter when no reminder of the chosen kind has gone', async () => {
    server.use(logHandler([]));
    renderWithProviders(<ReminderLog />);
    await screen.findByText('No reminders sent yet');

    await userEvent.selectOptions(screen.getByLabelText('Reminder'), 'first');

    expect(await screen.findByText('No reminders of this kind')).toBeInTheDocument();
  });
});
