import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { EmailLogEntry, Paginated } from '@/portal/api/types';
import { SEARCH_DEBOUNCE_MS } from '@/portal/components/useDebounced';
import { EmailLogPanel } from './EmailLogPanel';

/** A userEvent instance whose internal waits advance the fake clock instead of sleeping. */
function setupUser() {
  return userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
}

const ENTRIES: EmailLogEntry[] = [
  {
    id: 903,
    to_email: 'marta.reyes@example.org',
    user_id: 37,
    user_name: 'Marta Reyes',
    purpose: 'receipt',
    subject: 'CalDART: your receipt for $95.00',
    sent_at: '2026-01-08T09:00:02-08:00',
    status: 'sent',
    error: '',
    attachments: 'receipt-2026-0041.pdf',
  },
  {
    id: 902,
    to_email: 'unknown@example.org',
    user_id: null,
    user_name: '',
    purpose: 'password_reset',
    subject: 'CalDART: reset your password',
    sent_at: '2026-01-07T08:00:00-08:00',
    status: 'failed',
    error: 'SMTPRecipientsRefused',
    attachments: '',
  },
];

function page(rows: EmailLogEntry[]): Paginated<EmailLogEntry> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

function emailsHandler(rows: EmailLogEntry[]) {
  return http.get(`${API}/system/emails`, () => HttpResponse.json(page(rows)));
}

describe('EmailLogPanel', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows the most recent emails with their purpose, recipient and status', async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);

    const table = await screen.findByRole('table');
    const row = await within(table).findByRole('row', { name: /Marta Reyes/ });
    expect(row).toHaveTextContent('marta.reyes@example.org');
    expect(row).toHaveTextContent('Receipt');
    expect(row).toHaveTextContent('Sent');
    expect(row).toHaveTextContent('receipt-2026-0041.pdf');
  });

  it('reads a message with no account behind it by its address alone', async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);

    const table = await screen.findByRole('table');
    const row = await within(table).findByRole('row', { name: /unknown@example\.org/ });
    expect(row).toHaveTextContent('Password reset');
  });

  it('shows the error beside a failed send', async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);

    expect(await screen.findByText('Failed: SMTPRecipientsRefused')).toBeInTheDocument();
  });

  it('says nothing has gone out yet when the log is empty', async () => {
    server.use(emailsHandler([]));
    renderWithProviders(<EmailLogPanel />);

    expect(await screen.findByText('No emails sent yet')).toBeInTheDocument();
  });

  it('reports a failed fetch instead of reading silently as an empty log', async () => {
    server.use(
      http.get(`${API}/system/emails`, () =>
        HttpResponse.json({ detail: 'The database is unreachable.' }, { status: 500 }),
      ),
    );
    renderWithProviders(<EmailLogPanel />);

    expect(await screen.findByRole('alert')).toHaveTextContent('The database is unreachable.');
  });

  it('asks for fifty rows', async () => {
    const captured: string[] = [];
    server.use(
      http.get(`${API}/system/emails`, ({ request: req }) => {
        captured.push(new URL(req.url).searchParams.get('page_size') ?? '');
        return HttpResponse.json(page(ENTRIES));
      }),
    );
    renderWithProviders(<EmailLogPanel />);

    await screen.findByText('Marta Reyes');
    expect(captured[0]).toBe('50');
  });

  it('filters by purpose', async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);
    await screen.findByText('Marta Reyes');

    const captured: string[] = [];
    server.use(
      http.get(`${API}/system/emails`, ({ request: req }) => {
        captured.push(new URL(req.url).searchParams.get('purpose') ?? '');
        return HttpResponse.json(page(ENTRIES));
      }),
    );

    await userEvent.selectOptions(screen.getByLabelText('Purpose'), 'receipt');

    await waitFor(() => {
      expect(captured).toContain('receipt');
    });
  });

  it('debounces the search box before asking the server', async () => {
    const user = setupUser();
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);
    await screen.findByText('Marta Reyes');

    const captured: string[] = [];
    server.use(
      http.get(`${API}/system/emails`, ({ request: req }) => {
        captured.push(new URL(req.url).searchParams.get('q') ?? '');
        return HttpResponse.json(page(ENTRIES));
      }),
    );

    await user.type(screen.getByLabelText('Search'), 'reyes');
    await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS));

    // A single settled request, not one per keystroke: removing the debounce
    // would fail this with five captured values ('r', 're', ..., 'reyes').
    expect(captured).toEqual(['reyes']);
  });
});
