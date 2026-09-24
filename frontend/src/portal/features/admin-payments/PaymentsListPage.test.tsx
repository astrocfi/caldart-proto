import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { TEST_COLUMNS, makePayment } from '@test/fixtures/finance';
import { financeHandlers } from '@test/handlers';
import { renderWithProviders } from '@test/render';
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
    await user.click(screen.getByRole('button', { name: 'Clear filters' }));

    expect(screen.getByLabelText('Status')).toHaveValue('');
  });

  it('takes a cleared filter back out of the export link', async () => {
    const user = userEvent.setup();
    serveList();
    renderWithProviders(<PaymentsListPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    await user.selectOptions(screen.getByLabelText('Status'), 'succeeded');
    await user.click(screen.getByRole('button', { name: 'Clear filters' }));

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
      expect.stringContaining('/admin/payments/export.pdf'),
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
