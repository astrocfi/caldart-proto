import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { Paginated, ReminderLogEntry } from '@/portal/api/types';
import { AdminRemindersPage } from './AdminRemindersPage';

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
function logHandler(rows: ReminderLogEntry[]) {
  return http.get(`${API}/admin/reminders/log`, ({ request }) => {
    const kind = new URL(request.url).searchParams.get('kind');
    return HttpResponse.json(page(kind ? rows.filter((row) => row.kind === kind) : rows));
  });
}

describe('AdminRemindersPage', () => {
  it('heads the screen Reminders', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<AdminRemindersPage />);

    expect(await screen.findByRole('heading', { name: 'Reminders' })).toBeInTheDocument();
  });

  it('lists the reminders that have gone out', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<AdminRemindersPage />);

    expect(await screen.findByText('Marta Reyes')).toBeInTheDocument();
    expect(screen.getByText('owen@example.org')).toBeInTheDocument();
  });

  it('filters the list by kind', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<AdminRemindersPage />);
    await screen.findByText('Owen Delgado');

    await userEvent.selectOptions(screen.getByLabelText('Reminder'), 'post30');

    expect(await screen.findByText('1 reminder sent')).toBeInTheDocument();
    expect(screen.queryByText('Marta Reyes')).not.toBeInTheDocument();
  });

  it('offers no way to run the scan', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<AdminRemindersPage />);
    await screen.findByText('Marta Reyes');

    expect(screen.queryByRole('button', { name: 'Run now' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Dry run (send nothing)')).not.toBeInTheDocument();
  });

  it('explains the log as the record of what renewal emails were sent', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<AdminRemindersPage />);
    await screen.findByText('Marta Reyes');

    expect(
      screen.getByText(
        (_text, element) =>
          element?.tagName.toLowerCase() === 'p' &&
          element.textContent ===
            'The scan runs every morning at 07:00 and mails a member 60, 30, and 7 days before ' +
              'their membership ends, on the day it ends, and 30 days after. Each member gets ' +
              'one email per membership per kind. This is the record of what renewal emails ' +
              'were sent to each member.',
      ),
    ).toBeInTheDocument();
  });
});
