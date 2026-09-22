import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '../../../test/handlers';
import { renderWithProviders } from '../../../test/render';
import { server } from '../../../test/server';
import type { Paginated, ReminderLogEntry } from '../../api/types';
import { KIND_LABELS, ReminderLog } from './ReminderLog';

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

/** Log handler that honors the `kind` filter, like the API does. */
function logHandler(rows: ReminderLogEntry[], seen?: (kind: string | null) => void) {
  return http.get(`${API}/admin/reminders/log`, ({ request }) => {
    const kind = new URL(request.url).searchParams.get('kind');
    seen?.(kind);
    return HttpResponse.json(page(kind ? rows.filter((row) => row.kind === kind) : rows));
  });
}

describe('KIND_LABELS', () => {
  it('names every reminder the scanner sends', () => {
    expect(KIND_LABELS).toEqual({
      t60: '60 days before',
      t30: '30 days before',
      t7: '7 days before',
      expired: 'Expiry day',
      post30: '30 days after',
    });
  });
});

describe('ReminderLog', () => {
  it('lists recent reminders', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<ReminderLog />);

    expect(await screen.findByText('Marta Reyes')).toBeInTheDocument();
    // Scoped to the table: the kind filter uses the same labels.
    const table = within(screen.getByRole('table'));
    expect(table.getByText('30 days before')).toBeInTheDocument();
    expect(table.getByText('30 days after')).toBeInTheDocument();
    expect(table.getByText('marta@example.org')).toBeInTheDocument();
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

    await userEvent.selectOptions(screen.getByLabelText('Reminder'), 't30');

    await waitFor(() => expect(screen.queryByText('Owen Delgado')).not.toBeInTheDocument());
    expect(screen.getByText('Marta Reyes')).toBeInTheDocument();
    expect(kinds).toEqual([null, 't30']);
  });

  it('offers every kind plus "All kinds" in the filter', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<ReminderLog />);
    await screen.findByText('Marta Reyes');

    const options = within(screen.getByLabelText('Reminder')).getAllByRole('option');
    expect(options.map((option) => option.textContent)).toEqual([
      'All kinds',
      '60 days before',
      '30 days before',
      '7 days before',
      'Expiry day',
      '30 days after',
    ]);
  });

  it('carries no controls for running the scan', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<ReminderLog />);
    await screen.findByText('Marta Reyes');

    expect(screen.queryByRole('button', { name: 'Run now' })).not.toBeInTheDocument();
  });
});
