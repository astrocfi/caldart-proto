import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { TEST_COLUMNS, makePayment } from '@test/fixtures/finance';
import { API, financeHandlers } from '@test/handlers';
import { renderRoutes, renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { PaymentsListPage } from './PaymentsListPage';

/** Serve the list, its columns and the plan catalog, recording every URL. */
function serveList(payments = [makePayment()]): string[] {
  const urls: string[] = [];
  server.use(
    ...financeHandlers({
      urls,
      payments,
      columns: TEST_COLUMNS,
      plans: [
        { slug: 'annual', name: 'Annual', price_cents: 4_500, duration_days: 365, description: '' },
      ],
    }),
  );
  return urls;
}

describe('PaymentsListPage', () => {
  it('draws the default columns the registry names', async () => {
    serveList();
    renderWithProviders(<PaymentsListPage />);

    const table = await screen.findByRole('table', { name: /1 payment/ });
    const headers = within(table)
      .getAllByRole('columnheader')
      .map((cell) => cell.textContent?.replace(/[↑↓]/g, '').trim());
    expect(headers).toEqual(['Date', 'Name', 'Total', 'Fee', 'Net', 'Refunded', 'Status']);
  });

  it('links a row to its payment detail', async () => {
    serveList();
    renderWithProviders(<PaymentsListPage />);

    const table = await screen.findByRole('table', { name: /1 payment/ });
    expect(within(table).getByRole('link', { name: 'Marta Reyes' })).toHaveAttribute(
      'href',
      '/admin/payments/412',
    );
  });

  it('shows the fee the provider kept', async () => {
    serveList();
    renderWithProviders(<PaymentsListPage />);

    const table = await screen.findByRole('table', { name: /1 payment/ });
    expect(within(table).getByText('$4.50')).toBeInTheDocument();
  });

  it('sends a filter to the server', async () => {
    const user = userEvent.setup();
    const urls = serveList();
    renderWithProviders(<PaymentsListPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    await user.selectOptions(screen.getByLabelText('Reconciled'), 'no');

    await waitFor(() => expect(urls.some((url) => url.includes('reconciled=no'))).toBe(true));
  });

  it('reads its filters from the address, so a filtered list can be linked', async () => {
    const urls = serveList();
    renderWithProviders(<PaymentsListPage />, {
      route: '/admin/payments/list?provider=paypal&reconciled=no',
    });

    await screen.findByRole('table', { name: /1 payment/ });
    expect(screen.getByLabelText('Provider')).toHaveValue('paypal');
    expect(urls.some((url) => url.includes('reconciled=no'))).toBe(true);
  });

  it('offers the plans from the catalog', async () => {
    const user = userEvent.setup();
    const urls = serveList();
    renderWithProviders(<PaymentsListPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    await screen.findByRole('option', { name: 'Annual' });
    await user.selectOptions(screen.getByLabelText('Plan'), 'annual');

    await waitFor(() => expect(urls.some((url) => url.includes('plan=annual'))).toBe(true));
  });

  it('sends an amount typed in dollars as cents', async () => {
    const user = userEvent.setup();
    const urls = serveList();
    renderWithProviders(<PaymentsListPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    await user.type(screen.getByLabelText('At least'), '50');

    await waitFor(() => expect(urls.some((url) => url.includes('min_cents=5000'))).toBe(true));
  });

  it('points the exports at the payments report, in the order the table is sorted', async () => {
    serveList();
    renderWithProviders(<PaymentsListPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    expect(screen.getByRole('link', { name: /Export CSV/ })).toHaveAttribute(
      'href',
      '/api/v1/reports/payments/export.csv?ordering=-paid_at' +
        '&columns=paid_on%2Cname%2Ctotal%2Cfee%2Cnet%2Crefunded%2Cstatus',
    );
  });

  it('carries the filters into the CSV export link', async () => {
    const user = userEvent.setup();
    serveList();
    renderWithProviders(<PaymentsListPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    await user.selectOptions(screen.getByLabelText('Provider'), 'paypal');

    await waitFor(() =>
      expect(screen.getByRole('link', { name: /Export CSV/ })).toHaveAttribute(
        'href',
        expect.stringContaining('provider=paypal'),
      ),
    );
  });

  it('clears the filters again, on the controls and in the export link', async () => {
    const user = userEvent.setup();
    serveList();
    renderWithProviders(<PaymentsListPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    await user.selectOptions(screen.getByLabelText('Status'), 'succeeded');
    await user.click(screen.getByRole('button', { name: 'Clear' }));

    expect(screen.getByLabelText('Status')).toHaveValue('');
  });

  it('takes a cleared filter back out of the export link', async () => {
    const user = userEvent.setup();
    serveList();
    renderWithProviders(<PaymentsListPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    await user.selectOptions(screen.getByLabelText('Status'), 'succeeded');
    await user.click(screen.getByRole('button', { name: 'Clear' }));

    await waitFor(() =>
      expect(screen.getByRole('link', { name: /Export CSV/ })).not.toHaveAttribute(
        'href',
        expect.stringContaining('status='),
      ),
    );
  });

  it('offers a PDF export as well', async () => {
    serveList();
    renderWithProviders(<PaymentsListPage />);

    expect(await screen.findByRole('link', { name: /Export PDF/ })).toHaveAttribute(
      'href',
      expect.stringContaining('/api/v1/reports/payments/export.pdf'),
    );
  });

  it('adds a chosen column to the table', async () => {
    const user = userEvent.setup();
    serveList();
    renderWithProviders(<PaymentsListPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    await user.click(screen.getByRole('button', { name: 'Columns' }));
    await user.click(screen.getByRole('checkbox', { name: 'Receipt' }));

    const table = screen.getByRole('table', { name: /1 payment/ });
    expect(within(table).getByText('CALDART-000412')).toBeInTheDocument();
  });

  it('carries the chosen columns into the export link', async () => {
    const user = userEvent.setup();
    serveList();
    renderWithProviders(<PaymentsListPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    await user.click(screen.getByRole('button', { name: 'Columns' }));
    await user.click(screen.getByRole('checkbox', { name: 'Receipt' }));

    expect(screen.getByRole('link', { name: /Export CSV/ })).toHaveAttribute(
      'href',
      expect.stringContaining('receipt_number'),
    );
  });

  it('asks the server to reorder when a column header is clicked', async () => {
    const user = userEvent.setup();
    const urls = serveList();
    renderWithProviders(<PaymentsListPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    await user.click(screen.getByRole('button', { name: /Total/ }));

    await waitFor(() =>
      expect(urls.some((url) => url.includes('ordering=amount_cents'))).toBe(true),
    );
  });

  it('shows the order the address names, and follows it when the address changes', async () => {
    serveList();
    const { router } = renderRoutes(
      [{ path: '/admin/payments/list', element: <PaymentsListPage /> }],
      { route: '/admin/payments/list?ordering=user__last_name' },
    );
    await screen.findByRole('table', { name: /1 payment/ });
    expect(screen.getByRole('columnheader', { name: /Name/ })).toHaveAttribute(
      'aria-sort',
      'ascending',
    );

    await act(() => router.navigate('/admin/payments/list'));

    expect(screen.getByRole('columnheader', { name: /Date/ })).toHaveAttribute(
      'aria-sort',
      'descending',
    );
    expect(screen.getByRole('columnheader', { name: /Name/ })).toHaveAttribute('aria-sort', 'none');
  });

  it('asks for the first page when the address names a page that is not a positive whole number', async () => {
    const urls = serveList();
    renderWithProviders(<PaymentsListPage />, { route: '/admin/payments/list?page=-1' });

    await screen.findByRole('table', { name: /1 payment/ });
    const pages = urls
      .filter((url) => new URL(url).pathname.endsWith('/admin/payments'))
      .map((url) => new URL(url).searchParams.get('page'));
    expect(pages).toEqual(['1']);
  });

  it('goes back to the first page when the page the address names is past the end', async () => {
    const pages: (string | null)[] = [];
    serveList();
    server.use(
      http.get(`${API}/admin/payments`, ({ request }) => {
        const page = new URL(request.url).searchParams.get('page');
        pages.push(page);
        if (page !== '1') return HttpResponse.json({ detail: 'Invalid page.' }, { status: 404 });
        return HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [makePayment()],
        });
      }),
    );
    renderWithProviders(<PaymentsListPage />, { route: '/admin/payments/list?page=7' });

    expect(await screen.findByRole('table', { name: /1 payment/ })).toBeInTheDocument();
    expect(pages).toEqual(['7', '1']);
  });

  it('shows an empty state when nothing matches', async () => {
    serveList([]);
    renderWithProviders(<PaymentsListPage />);

    expect(await screen.findByText('No payments match these filters')).toBeInTheDocument();
  });

  it('offers the record form', async () => {
    serveList();
    renderWithProviders(<PaymentsListPage />);

    expect(await screen.findByRole('link', { name: 'Record a payment' })).toHaveAttribute(
      'href',
      '/admin/payments/record',
    );
  });
});
