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
    purpose_label: 'Receipt',
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
    purpose_label: 'Password reset',
    subject: 'CalDART: reset your password',
    sent_at: '2026-01-07T08:00:00-08:00',
    status: 'failed',
    error: 'SMTPRecipientsRefused',
    attachments: '',
  },
];

function page(
  rows: EmailLogEntry[],
  { count = rows.length, next = null, previous = null }: Partial<Paginated<EmailLogEntry>> = {},
): Paginated<EmailLogEntry> {
  return { count, next, previous, results: rows };
}

function emailsHandler(rows: EmailLogEntry[]) {
  return http.get(`${API}/system/emails`, () => HttpResponse.json(page(rows)));
}

/** Answers every page with `rows` and records each request's query string. */
function capturingHandler(captured: URLSearchParams[], body: Paginated<EmailLogEntry>) {
  return http.get(`${API}/system/emails`, ({ request: req }) => {
    captured.push(new URL(req.url).searchParams);
    return HttpResponse.json(body);
  });
}

describe('EmailLogPanel', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows each email with its purpose, recipient and status', async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);

    const table = await screen.findByRole('table');
    const row = await within(table).findByRole('row', { name: /Marta Reyes/ });
    expect(row).toHaveTextContent('marta.reyes@example.org');
    expect(row).toHaveTextContent('Receipt');
    expect(row).toHaveTextContent('Sent');
    expect(row).toHaveTextContent('receipt-2026-0041.pdf');
  });

  it("reads the purpose from the server's label", async () => {
    const [first] = ENTRIES;
    if (first === undefined) throw new Error('ENTRIES is empty');
    server.use(emailsHandler([{ ...first, purpose: 'board_minutes', purpose_label: 'Minutes' }]));
    renderWithProviders(<EmailLogPanel />);

    const row = await screen.findByRole('row', { name: /Marta Reyes/ });
    expect(row).toHaveTextContent('Minutes');
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

  it("offers the server's purposes in the purpose filter", async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);

    const select = screen.getByLabelText('Purpose');
    await waitFor(() => {
      expect(within(select).getByRole('option', { name: 'Password reset' })).toBeInTheDocument();
    });
  });

  it('asks for the standard page, newest first', async () => {
    const captured: URLSearchParams[] = [];
    server.use(capturingHandler(captured, page(ENTRIES)));
    renderWithProviders(<EmailLogPanel />);

    await screen.findByText('Marta Reyes');
    expect(captured[0]?.toString()).toBe('ordering=-sent_at');
  });

  it('filters by purpose', async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);
    await screen.findByText('Marta Reyes');
    const captured: URLSearchParams[] = [];
    server.use(capturingHandler(captured, page(ENTRIES)));

    const select = screen.getByLabelText('Purpose');
    await within(select).findByRole('option', { name: 'Receipt' });
    await userEvent.selectOptions(select, 'receipt');

    await waitFor(() => {
      expect(captured.map((params) => params.get('purpose'))).toContain('receipt');
    });
  });

  it('filters by status', async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);
    await screen.findByText('Marta Reyes');
    const captured: URLSearchParams[] = [];
    server.use(capturingHandler(captured, page(ENTRIES)));

    await userEvent.selectOptions(screen.getByLabelText('Status'), 'failed');

    await waitFor(() => {
      expect(captured.map((params) => params.get('status'))).toContain('failed');
    });
  });

  it('reads a date range from the address', async () => {
    const captured: URLSearchParams[] = [];
    server.use(capturingHandler(captured, page(ENTRIES)));
    renderWithProviders(<EmailLogPanel />, { route: '/system?from=2026-01-01&to=2026-01-31' });

    await screen.findByText('Marta Reyes');
    expect([captured[0]?.get('from'), captured[0]?.get('to')]).toEqual([
      '2026-01-01',
      '2026-01-31',
    ]);
  });

  it('debounces the search box before asking the server', async () => {
    const user = setupUser();
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);
    await screen.findByText('Marta Reyes');
    const captured: URLSearchParams[] = [];
    server.use(capturingHandler(captured, page(ENTRIES)));

    await user.type(screen.getByLabelText('Search'), 'reyes');
    await act(() => vi.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS));

    // A single settled request, not one per keystroke: removing the debounce
    // would fail this with five captured values ('r', 're', ..., 'reyes').
    await waitFor(() => {
      expect(captured.map((params) => params.get('q'))).toEqual(['reyes']);
    });
  });

  it('counts the rows of a long log and pages through it', async () => {
    const [first] = ENTRIES;
    if (first === undefined) throw new Error('ENTRIES is empty');
    const fullPage = Array.from({ length: 25 }, (_unused, index) => ({ ...first, id: index + 1 }));
    const captured: URLSearchParams[] = [];
    server.use(
      capturingHandler(
        captured,
        page(fullPage, { count: 60, next: `${API}/system/emails?page=2` }),
      ),
    );
    renderWithProviders(<EmailLogPanel />);

    expect(await screen.findByText('Showing 1–25 of 60')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => {
      expect(captured.map((params) => params.get('page'))).toContain('2');
    });
  });

  it('shows no pager when the log fits on one page', async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);

    await screen.findByText('Marta Reyes');
    expect(screen.queryByRole('button', { name: 'Next' })).not.toBeInTheDocument();
  });

  it('downloads the email log report with the filters the table shows', async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />, { route: '/system?status=failed&page=2' });

    const link = await screen.findByRole('link', { name: 'Export CSV' });
    expect(link).toHaveAttribute(
      'href',
      '/api/v1/reports/emails/export.csv?status=failed&ordering=-sent_at',
    );
  });

  it('offers the same download as a PDF', async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);

    const link = await screen.findByRole('link', { name: 'Export PDF' });
    expect(link).toHaveAttribute('href', '/api/v1/reports/emails/export.pdf?ordering=-sent_at');
  });
});
