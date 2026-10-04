import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import type { DonorRow, ReportColumn } from '@/portal/api/types';
import { API, makeDonorRow } from '@test/handlers';
import { renderWithProviders, signedInClient } from '@test/render';
import { server } from '@test/server';
import { API_BASE } from '@/portal/urlPrefix';
import { DonorsPage } from './DonorsPage';

/** The donors report's column registry, matching the server's default set. */
const DONOR_COLUMNS: ReportColumn[] = [
  { key: 'name', label: 'Name', default: true },
  { key: 'email', label: 'Email', default: true },
  { key: 'phone', label: 'Phone', default: true },
  { key: 'city', label: 'City', default: true },
  { key: 'state', label: 'State', default: true },
  { key: 'county', label: 'County', default: false },
  { key: 'dart', label: 'DART', default: false },
  { key: 'first_gift', label: 'First gift', default: true },
  { key: 'last_gift', label: 'Last gift', default: true },
  { key: 'gifts', label: 'Gifts', default: true },
  { key: 'given', label: 'Given', default: true },
  { key: 'refunded', label: 'Refunded', default: false },
  { key: 'net', label: 'Net', default: true },
  { key: 'active', label: 'Active', default: false },
];

/** The row that keeps a deleted donor's gifts, whose record cannot be changed. */
const TOMBSTONE_ROW = makeDonorRow({
  user_id: 77,
  name: 'Deleted member 41',
  email: 'deleted-41@deleted.invalid',
  is_tombstone: true,
});

const DANA = makeDonorRow({
  user_id: 41,
  dart: 'East Bay DART',
  last_gift: '2026-06-20',
  gifts: 2,
  refunded_cents: 1000,
  net_cents: 4000,
});

/** Answer the donors call and the column registry, recording every query parameter seen. */
function donorsHandlers(rows: DonorRow[], seen: URLSearchParams[] = []) {
  return [
    http.get(`${API}/admin/payments/donors`, ({ request }) => {
      seen.push(new URL(request.url).searchParams);
      return HttpResponse.json(rows);
    }),
    http.get(`${API}/reports/donors/columns`, () => HttpResponse.json(DONOR_COLUMNS)),
  ];
}

/** The page also reads the DART list for its filter's options; empty by default. */
beforeEach(() => {
  server.use(http.get(`${API}/darts`, () => HttpResponse.json([])));
});

describe('DonorsPage', () => {
  it('shows what a donor has given, what came back, and the net', async () => {
    server.use(...donorsHandlers([DANA]));
    renderWithProviders(<DonorsPage />);

    const row = within(await screen.findByRole('row', { name: /Dana Doe/ }));
    expect(row.getByText('$50.00')).toBeInTheDocument();
    expect(row.getByText('$40.00')).toBeInTheDocument();
  });

  it('shows the first and last gift dates', async () => {
    server.use(...donorsHandlers([DANA]));
    renderWithProviders(<DonorsPage />);

    const row = within(await screen.findByRole('row', { name: /Dana Doe/ }));
    expect(row.getByText('01/10/2026')).toBeInTheDocument();
    expect(row.getByText('06/20/2026')).toBeInTheDocument();
  });

  it('draws the default columns the registry names', async () => {
    server.use(...donorsHandlers([DANA]));
    renderWithProviders(<DonorsPage />);

    await screen.findByRole('row', { name: /Dana Doe/ });
    const table = screen.getByRole('table', { name: '1 donor' });
    const headers = within(table)
      .getAllByRole('columnheader')
      .map((cell) => cell.textContent?.replace(/[↑↓↕]/g, '').trim());
    expect(headers).toEqual([
      'Name',
      'Email',
      'Phone',
      'City',
      'State',
      'First gift',
      'Last gift',
      'Gifts',
      'Given',
      'Net',
    ]);
  });

  it('sends a chosen county filter to the server', async () => {
    const seen: URLSearchParams[] = [];
    server.use(...donorsHandlers([DANA], seen));
    renderWithProviders(<DonorsPage />, { route: '/admin/payments/donors?county=Alameda,Marin' });

    await screen.findByRole('row', { name: /Dana Doe/ });

    expect(seen.at(-1)?.get('county')).toBe('Alameda,Marin');
  });

  it('points the exports at the donors report with the filters and columns applied', async () => {
    server.use(...donorsHandlers([DANA]));
    renderWithProviders(<DonorsPage />, { route: '/admin/payments/donors?search=Dana' });
    await screen.findByRole('row', { name: /Dana Doe/ });

    expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
      'href',
      `${API_BASE}/reports/donors/export.csv?search=Dana` +
        '&columns=name%2Cemail%2Cphone%2Ccity%2Cstate%2Cfirst_gift%2Clast_gift%2Cgifts%2Cgiven%2Cnet',
    );
  });

  it('adds a chosen column to the table and to the export link', async () => {
    const user = userEvent.setup();
    server.use(...donorsHandlers([DANA]));
    renderWithProviders(<DonorsPage />);

    await screen.findByRole('row', { name: /Dana Doe/ });
    await user.click(screen.getByRole('button', { name: 'Columns' }));
    await user.click(screen.getByRole('checkbox', { name: 'County' }));

    const table = screen.getByRole('table', { name: '1 donor' });
    expect(within(table).getByText('Contra Costa')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('county'),
    );
  });

  it("links a donor's name to their record for a treasurer who is an account administrator", async () => {
    server.use(...donorsHandlers([DANA]));
    renderWithProviders(<DonorsPage />, { client: signedInClient('treasurer', 'account_admin') });

    expect(await screen.findByRole('link', { name: 'Dana Doe' })).toHaveAttribute(
      'href',
      '/admin/members/41',
    );
  });

  it("links a donor's name to their record for a system administrator", async () => {
    server.use(...donorsHandlers([DANA]));
    renderWithProviders(<DonorsPage />, { client: signedInClient('system_admin') });

    expect(await screen.findByRole('link', { name: 'Dana Doe' })).toHaveAttribute(
      'href',
      '/admin/members/41',
    );
  });

  it('shows a treasurer who cannot open member records the name without a link', async () => {
    server.use(...donorsHandlers([DANA]));
    renderWithProviders(<DonorsPage />, { client: signedInClient('treasurer') });

    await screen.findByRole('row', { name: /Dana Doe/ });

    expect(screen.queryByRole('link', { name: 'Dana Doe' })).not.toBeInTheDocument();
  });

  it("leaves the row of a deleted donor's gifts unlinked", async () => {
    server.use(...donorsHandlers([DANA, TOMBSTONE_ROW]));
    renderWithProviders(<DonorsPage />, { client: signedInClient('treasurer', 'account_admin') });

    await screen.findByRole('link', { name: 'Dana Doe' });

    expect(screen.queryByRole('link', { name: 'Deleted member 41' })).not.toBeInTheDocument();
  });

  it('says so when no donor matches the filters', async () => {
    server.use(...donorsHandlers([]));
    renderWithProviders(<DonorsPage />);

    expect(await screen.findByText('No donors match')).toBeInTheDocument();
  });

  it('offers to reset the filters from an empty list', async () => {
    const user = userEvent.setup();
    server.use(...donorsHandlers([]));
    renderWithProviders(<DonorsPage />, { route: '/admin/payments/donors?search=nobody' });

    await screen.findByText('No donors match');
    const resets = screen.getAllByRole('button', { name: 'Reset filters' });
    await user.click(resets[resets.length - 1]!);

    expect(screen.getByLabelText('Search')).toHaveValue('');
  });

  it('opens on the arrow of the order the list comes in, most given first', async () => {
    server.use(...donorsHandlers([DANA]));
    renderWithProviders(<DonorsPage />);

    await screen.findByRole('row', { name: /Dana Doe/ });
    expect(screen.getByRole('columnheader', { name: /Net/ })).toHaveAttribute(
      'aria-sort',
      'descending',
    );
  });

  it('shows a failed call as a failure', async () => {
    server.use(
      http.get(`${API}/admin/payments/donors`, () => new HttpResponse(null, { status: 500 })),
    );
    renderWithProviders(<DonorsPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "The donors didn't load. Try again in a moment.",
    );
  });
});
