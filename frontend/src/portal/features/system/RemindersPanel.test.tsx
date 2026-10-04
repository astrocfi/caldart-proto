import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeReminderSchedule } from '@test/fixtures/reminders';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { Paginated, ReminderLogEntry } from '@/portal/api/types';
import { EmailLogPanel } from './EmailLogPanel';
import { RemindersPanel } from './RemindersPanel';

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
    kind: 'second' as const,
    member: 'Marta Reyes',
    email: 'marta@example.org',
    on: '2026-07-15',
    amount_cents: null,
    detail: '',
  },
];

describe('RemindersPanel', () => {
  it('names the days of the stored schedule', async () => {
    server.use(
      logHandler(ENTRIES),
      http.get(`${API}/admin/reminders/schedule`, () =>
        HttpResponse.json(makeReminderSchedule({ first_days_before: 90, lapsed_days_after: 14 })),
      ),
    );
    renderWithProviders(<RemindersPanel />);

    expect(
      await screen.findByText(
        /has just expired: 90, 30, and 7 days before, on the day, and 14 days after\./,
      ),
    ).toBeInTheDocument();
  });

  it('shows the reminder log under its own heading, below Run now', async () => {
    server.use(logHandler(ENTRIES));
    renderWithProviders(<RemindersPanel />);

    expect(await screen.findByText('Marta Reyes')).toBeInTheDocument();
    const heading = screen.getByRole('heading', { name: 'Reminders sent' });
    const button = screen.getByRole('button', { name: 'Run now: renewal reminder emails' });
    expect(button.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0);
  });

  it('says only that nothing is due when a practice run finds nothing at all', async () => {
    server.use(
      logHandler(ENTRIES),
      http.post(`${API}/system/reminders/run`, () =>
        HttpResponse.json({ sent: 0, skipped: 0, failed: 0, skipped_by_reason: {}, actions: [] }),
      ),
    );
    renderWithProviders(<RemindersPanel />);
    await screen.findByText('Marta Reyes');

    await userEvent.click(screen.getByRole('button', { name: 'Run now: renewal reminder emails' }));

    expect(await screen.findByRole('status')).toHaveTextContent(/^Nothing is due\.$/);
    expect(screen.queryByText(/Would send/)).toBeNull();
  });

  it('runs a practice run by default and reports the result', async () => {
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

    expect(
      screen.getByLabelText(
        'Practice run: show what would happen, send nothing (renewal reminder emails)',
      ),
    ).toBeChecked();
    await userEvent.click(screen.getByRole('button', { name: 'Run now: renewal reminder emails' }));

    expect(await screen.findByText('Would send 4 emails, skipped 2.')).toBeInTheDocument();
    expect(bodies).toEqual([{ dry_run: true }]);
    expect(screen.getByRole('heading', { name: 'What this run would do' })).toBeInTheDocument();
    const actionsTable = screen.getByRole('table', { name: '1 action' });
    const row = within(actionsTable).getByRole('row', { name: /Marta Reyes/ });
    expect(row).toHaveTextContent('Second reminder (30 days before)');
    expect(row).toHaveTextContent('07/15/2026');
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

    await userEvent.click(screen.getByRole('button', { name: 'Run now: renewal reminder emails' }));

    expect(await screen.findByText('Nothing was due')).toBeInTheDocument();
  });

  it('sends for real once the practice-run box is cleared', async () => {
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

    await userEvent.click(
      screen.getByLabelText(
        'Practice run: show what would happen, send nothing (renewal reminder emails)',
      ),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Run now: renewal reminder emails' }));

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

    await userEvent.click(screen.getByRole('button', { name: 'Run now: renewal reminder emails' }));

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

    await userEvent.click(screen.getByRole('button', { name: 'Run now: renewal reminder emails' }));

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

    await userEvent.click(screen.getByRole('button', { name: 'Run now: renewal reminder emails' }));

    await screen.findByText('Would send 1 email, skipped 0.');
    expect(screen.queryByText(/^Skipped:/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Failed/)).not.toBeInTheDocument();
  });

  it('refreshes the email log after a live run, so its new rows show up', async () => {
    // The email log on /portal/system/emails reads the same 'system','emails' query key a
    // live run's onSuccess invalidates, so the log is fresh when the reader opens it.
    let emailRequests = 0;
    server.use(
      logHandler(ENTRIES),
      http.get(`${API}/system/emails`, () => {
        emailRequests += 1;
        return HttpResponse.json({ count: 0, next: null, previous: null, results: [] });
      }),
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
    renderWithProviders(
      <>
        <RemindersPanel />
        <EmailLogPanel />
      </>,
    );
    await screen.findByText('Marta Reyes');
    await waitFor(() => expect(emailRequests).toBe(1));

    await userEvent.click(
      screen.getByLabelText(
        'Practice run: show what would happen, send nothing (renewal reminder emails)',
      ),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Run now: renewal reminder emails' }));
    await screen.findByText('Sent 1 email, skipped 0.');

    await waitFor(() => {
      expect(emailRequests).toBe(2);
    });
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

    await userEvent.click(screen.getByRole('button', { name: 'Run now: renewal reminder emails' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('SMTP refused the connection');
  });
});
