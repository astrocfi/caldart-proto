import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { EmailLogEntry, Paginated, ReportColumn } from '@/portal/api/types';
import { SEARCH_DEBOUNCE_MS } from '@/portal/components/useDebounced';
import { API_BASE } from '@/portal/urlPrefix';
import { reportTableColumns } from '@/portal/components/reportTable';
import { fitColumns } from '@/portal/components/tableFit';
import { CELLS, EmailLogPanel } from './EmailLogPanel';

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
    bounced_at: null,
    bounce_detail: '',
    link: '',
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
    bounced_at: null,
    bounce_detail: '',
    link: '',
  },
];

/** A reminder the bounce check found bouncing, at noon UTC on October 1st, 2026. */
const BOUNCED: EmailLogEntry = {
  id: 904,
  to_email: 'gone@example.com',
  user_id: 41,
  user_name: 'Dana Doe',
  purpose: 'reminder_second',
  purpose_label: 'Second reminder (30 days before)',
  subject: 'CalDART: your membership expires in 30 days',
  sent_at: '2026-10-01T08:00:00-07:00',
  status: 'bounced',
  error: '',
  attachments: '',
  bounced_at: '2026-10-01T12:00:00Z',
  bounce_detail: '5.1.1 550 User unknown',
  link: '',
};

function page(
  rows: EmailLogEntry[],
  { count = rows.length, next = null, previous = null }: Partial<Paginated<EmailLogEntry>> = {},
): Paginated<EmailLogEntry> {
  return { count, next, previous, results: rows };
}

/** The email log report's registry, as the server answers it, with `extra` checked too. */
function registry(...extra: string[]): ReportColumn[] {
  const columns: [string, string, boolean][] = [
    ['sent_at', 'Sent', true],
    ['purpose', 'Purpose', true],
    ['to_email', 'To', true],
    ['user_name', 'Name', true],
    ['subject', 'Subject', true],
    ['status', 'Status', true],
    ['error', 'Error', false],
    ['attachments', 'Attachments', false],
    ['bounced_at', 'Bounced', false],
    ['bounce_detail', 'Bounce detail', false],
  ];
  return columns.map(([key, label, isDefault]) => ({
    key,
    label,
    default: isDefault || extra.includes(key),
  }));
}

function registryHandler(columns: ReportColumn[]) {
  return http.get(`${API}/reports/emails/columns`, () => HttpResponse.json(columns));
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
    expect(row).toHaveTextContent('CalDART: your receipt for $95.00');
  });

  it('opens each email on its own page from the address it went to', async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);

    const link = await screen.findByRole('link', { name: /^marta\.reyes@example\.org, sent / });
    expect(link).toHaveAttribute('href', '/system/emails/903');
  });

  it('shows the columns checked in the chooser, such as the attachments', async () => {
    server.use(emailsHandler(ENTRIES), registryHandler(registry('attachments')));
    renderWithProviders(<EmailLogPanel />);

    const row = await screen.findByRole('row', { name: /receipt-2026-0041\.pdf/ });
    expect(row).toHaveTextContent('Marta Reyes');
  });

  it('adds a column to the table when it is checked in the chooser', async () => {
    server.use(emailsHandler(ENTRIES), registryHandler(registry()));
    renderWithProviders(<EmailLogPanel />);

    await screen.findByRole('columnheader', { name: 'Subject' });
    await userEvent.click(screen.getByRole('button', { name: 'Columns' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Error' }));

    expect(screen.getByRole('columnheader', { name: 'Error' })).toBeInTheDocument();
  });

  it('carries a checked column into the downloads', async () => {
    server.use(emailsHandler(ENTRIES), registryHandler(registry()));
    renderWithProviders(<EmailLogPanel />);

    await screen.findByRole('columnheader', { name: 'Subject' });
    await userEvent.click(screen.getByRole('button', { name: 'Columns' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Error' }));

    expect(screen.getByRole('link', { name: 'Export CSV' }).getAttribute('href')).toContain(
      'columns=sent_at%2Cpurpose%2Cto_email%2Cuser_name%2Csubject%2Cstatus%2Cerror',
    );
  });

  it('shows the newest first with the arrow on Sent', async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);

    expect(await screen.findByRole('columnheader', { name: /Sent/ })).toHaveAttribute(
      'aria-sort',
      'descending',
    );
  });

  it("reads the purpose from the server's label", async () => {
    const [first] = ENTRIES;
    if (first === undefined) throw new Error('ENTRIES is empty');
    server.use(emailsHandler([{ ...first, purpose: 'board_minutes', purpose_label: 'Minutes' }]));
    renderWithProviders(<EmailLogPanel />);

    const row = await screen.findByRole('row', { name: /Marta Reyes/ });
    expect(row).toHaveTextContent('Minutes');
  });

  it("links a bulk email's copy to the bulk email", async () => {
    const [first] = ENTRIES;
    if (first === undefined) throw new Error('ENTRIES is empty');
    server.use(
      emailsHandler([
        {
          ...first,
          purpose: 'bulk_email',
          purpose_label: 'Bulk email',
          link: '/bulk-email/sent/9',
        },
      ]),
    );
    renderWithProviders(<EmailLogPanel />);

    expect(await screen.findByRole('link', { name: 'Bulk email' })).toHaveAttribute(
      'href',
      '/bulk-email/sent/9',
    );
  });

  it('links no message that belongs to no record', async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);

    await screen.findByRole('row', { name: /Marta Reyes/ });
    expect(screen.queryByRole('link', { name: 'Receipt' })).toBeNull();
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

  it('reads a bounced message as Bounced', async () => {
    server.use(emailsHandler([BOUNCED]));
    renderWithProviders(<EmailLogPanel />);

    const row = await screen.findByRole('row', { name: /Dana Doe/ });
    expect(
      within(row)
        .getAllByRole('cell')
        .map((cell) => cell.textContent),
    ).toContain('Bounced');
  });

  it('shows when a message bounced and the report, once those columns are checked', async () => {
    server.use(emailsHandler([BOUNCED]), registryHandler(registry('bounced_at', 'bounce_detail')));
    renderWithProviders(<EmailLogPanel />);

    const row = await screen.findByRole('row', { name: /5\.1\.1 550 User unknown/ });
    expect(row).toHaveTextContent('10/01/2026');
  });

  it('says nothing has gone out yet when the log is empty', async () => {
    server.use(emailsHandler([]));
    renderWithProviders(<EmailLogPanel />);

    expect(await screen.findByText('No emails sent yet')).toBeInTheDocument();
  });

  it('offers to reset the filters when nothing matches them', async () => {
    server.use(emailsHandler([]));
    renderWithProviders(<EmailLogPanel />, { route: '/system?status=failed' });

    await screen.findByText('No emails match these filters');
    await userEvent.click(screen.getAllByRole('button', { name: 'Reset filters' }).at(-1)!);

    expect(await screen.findByLabelText('Status')).toHaveValue('');
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

  it('offers the bounced messages as a status', async () => {
    server.use(emailsHandler(ENTRIES));
    renderWithProviders(<EmailLogPanel />);
    await screen.findByText('Marta Reyes');
    const captured: URLSearchParams[] = [];
    server.use(capturingHandler(captured, page([BOUNCED])));

    await userEvent.selectOptions(screen.getByLabelText('Status'), 'Bounced');

    await waitFor(() => {
      expect(captured.map((params) => params.get('status'))).toContain('bounced');
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
        page(fullPage, { count: 60, next: `${API_BASE}/system/emails?page=2` }),
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

describe('the sent emails table at narrow widths', () => {
  const DEFAULTS: ReportColumn[] = [
    { key: 'sent_at', label: 'Sent', default: true },
    { key: 'purpose', label: 'Purpose', default: true },
    { key: 'to_email', label: 'To', default: true },
    { key: 'user_name', label: 'Name', default: true },
    { key: 'subject', label: 'Subject', default: true },
    { key: 'status', label: 'Status', default: true },
  ];
  const columns = reportTableColumns(
    DEFAULTS,
    DEFAULTS.map((column) => column.key),
    CELLS,
    true,
  );

  it.each([
    ['a tablet', 46],
    ['a phone', 19],
  ])('keeps To, the column the screen exists for, on %s', (_width, rem) => {
    expect(fitColumns(columns, rem).map((column) => column.header)).toContain('To');
  });

  it('pins To at the left as the table scrolls', () => {
    expect(fitColumns(columns, 19).find((column) => column.isIdentity)?.header).toBe('To');
  });

  it('keeps the subject beside the address on a tablet', () => {
    expect(fitColumns(columns, 46).map((column) => column.header)).toContain('Subject');
  });
});
