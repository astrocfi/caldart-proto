import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { financeHandlers } from '@test/handlers';
import { makePeriod } from '@test/fixtures/finance';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { AdminPaymentsPage } from './AdminPaymentsPage';

const MONTHS = [
  makePeriod({ period: '2025-11', count: 2, total_cents: 9_000, refunded_cents: 0 }),
  makePeriod(),
];

/** Serve the summary the overview reads, recording every request URL. */
function serveOverview(): string[] {
  const urls: string[] = [];
  server.use(...financeHandlers({ urls, summary: MONTHS }));
  return urls;
}

describe('AdminPaymentsPage', () => {
  it('shows the three headline tiles', async () => {
    serveOverview();
    renderWithProviders(<AdminPaymentsPage />);

    expect(await screen.findByText('This month')).toBeInTheDocument();
  });

  it('names every period the tiles cover', async () => {
    serveOverview();
    renderWithProviders(<AdminPaymentsPage />);

    await screen.findByText('This month');
    expect(screen.getByText('Last 12 months')).toBeInTheDocument();
  });

  it('renders the period table with a column per provider and the fee columns', async () => {
    serveOverview();
    renderWithProviders(<AdminPaymentsPage />);

    const table = await screen.findByRole('table', { name: /Payment totals by month/ });
    const headers = within(table)
      .getAllByRole('columnheader')
      .map((cell) => cell.textContent);
    expect(headers).toEqual([
      'Month',
      'Payments',
      'Dues',
      'Contributions',
      'Stripe',
      'PayPal',
      'Fees',
      'Net',
      'Refunded',
      'Total',
    ]);
  });

  it('puts the newest period first', async () => {
    serveOverview();
    renderWithProviders(<AdminPaymentsPage />);

    const table = await screen.findByRole('table', { name: /by month/ });
    const first = within(table).getAllByRole('row')[1];
    expect(within(first!).getByRole('rowheader')).toHaveTextContent('Jan 2026');
  });

  it('reports what went back out of a period', async () => {
    serveOverview();
    renderWithProviders(<AdminPaymentsPage />);

    const table = await screen.findByRole('table', { name: /by month/ });
    const first = within(table).getAllByRole('row')[1];
    expect(first!).toHaveTextContent('$25.00');
  });

  it('switches the period table to years', async () => {
    const user = userEvent.setup();
    const urls = serveOverview();
    renderWithProviders(<AdminPaymentsPage />);

    await user.click(await screen.findByRole('button', { name: 'Year' }));

    await waitFor(() => expect(urls.some((url) => url.includes('group=year'))).toBe(true));
  });

  it('sends the overview filter to the server', async () => {
    const user = userEvent.setup();
    const urls = serveOverview();
    renderWithProviders(<AdminPaymentsPage />);

    await screen.findByRole('table', { name: /by month/ });
    await user.selectOptions(screen.getByLabelText('Provider'), 'paypal');

    await waitFor(() => expect(urls.some((url) => url.includes('provider=paypal'))).toBe(true));
  });

  it('links on to the payment list', async () => {
    serveOverview();
    renderWithProviders(<AdminPaymentsPage />);

    expect(await screen.findByRole('link', { name: 'All payments' })).toHaveAttribute(
      'href',
      '/admin/payments/list',
    );
  });
});
