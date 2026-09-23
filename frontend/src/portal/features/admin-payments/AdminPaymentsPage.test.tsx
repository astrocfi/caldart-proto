import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { Payment, PaymentPeriodSummary } from '@/portal/api/types';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { AdminPaymentsPage } from './AdminPaymentsPage';

const SUMMARY: PaymentPeriodSummary[] = [
  {
    period: '2025-11',
    count: 2,
    total_cents: 9_000,
    plan_cents: 9_000,
    contribution_cents: 0,
    by_provider: { stripe: 4_500, paypal: 4_500 },
  },
  {
    period: '2026-01',
    count: 2,
    total_cents: 21_000,
    plan_cents: 9_000,
    contribution_cents: 12_000,
    by_provider: { stripe: 14_500, paypal: 6_500 },
  },
];

const YEARS: PaymentPeriodSummary[] = [
  {
    period: '2026',
    count: 4,
    total_cents: 30_000,
    plan_cents: 18_000,
    contribution_cents: 12_000,
    by_provider: { stripe: 19_000, paypal: 11_000 },
  },
];

function payment(overrides: Partial<Payment> = {}): Payment {
  return {
    id: 1,
    user_id: 3,
    user_name: 'Marta Reyes',
    plan: 'Annual',
    amount_cents: 14_500,
    plan_amount_cents: 4_500,
    contribution_cents: 10_000,
    currency: 'usd',
    provider: 'stripe',
    wallet: 'apple_pay',
    provider_ref: 'pi_123',
    status: 'succeeded',
    created_at: '2026-01-08T20:00:00Z',
    completed_at: '2026-01-08T20:00:05Z',
    ...overrides,
  };
}

/** Serve the three endpoints the page uses, recording every request URL. */
function serveDashboard(rows: Payment[] = [payment()]) {
  const urls: string[] = [];
  server.use(
    http.get(`${API}/admin/payments/summary`, ({ request }) => {
      urls.push(request.url);
      const group = new URL(request.url).searchParams.get('group');
      return HttpResponse.json(group === 'year' ? YEARS : SUMMARY);
    }),
    http.get(`${API}/admin/payments`, ({ request }) => {
      urls.push(request.url);
      return HttpResponse.json({
        count: rows.length,
        next: null,
        previous: null,
        results: rows,
      });
    }),
  );
  return urls;
}

describe('AdminPaymentsPage', () => {
  it('shows the three headline tiles', async () => {
    serveDashboard();
    renderWithProviders(<AdminPaymentsPage />);

    expect(await screen.findByText('This month')).toBeInTheDocument();
    expect(screen.getByText('Year to date')).toBeInTheDocument();
    expect(screen.getByText('Last 12 months')).toBeInTheDocument();
  });

  it('renders the period table with a column per provider', async () => {
    serveDashboard();
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
      'Total',
    ]);

    // Newest period first.
    const first = within(table).getAllByRole('row')[1];
    expect(within(first!).getByRole('rowheader')).toHaveTextContent('January 2026');
    expect(first!).toHaveTextContent('$145.00');
    expect(first!).toHaveTextContent('$65.00');
  });

  it('switches the period table to years', async () => {
    const user = userEvent.setup();
    serveDashboard();
    renderWithProviders(<AdminPaymentsPage />);

    await screen.findByRole('table', { name: /by month/ });
    await user.click(screen.getByRole('button', { name: 'Year' }));

    const table = await screen.findByRole('table', { name: /by year/ });
    expect(within(table).getByRole('rowheader')).toHaveTextContent('2026');
    expect(screen.getByRole('button', { name: 'Year' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('lists payments with member, method, and status', async () => {
    serveDashboard();
    renderWithProviders(<AdminPaymentsPage />);

    const table = await screen.findByRole('table', { name: /1 payment/ });
    expect(within(table).getByText('Marta Reyes')).toBeInTheDocument();
    expect(within(table).getByText(/Apple Pay/)).toBeInTheDocument();
    expect(within(table).getByText('Succeeded')).toBeInTheDocument();
    expect(within(table).getByText('$145.00')).toBeInTheDocument();
  });

  it('sends the filters to the server and reflects them in the export link', async () => {
    const user = userEvent.setup();
    const urls = serveDashboard();
    renderWithProviders(<AdminPaymentsPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    await user.selectOptions(screen.getByLabelText('Provider'), 'paypal');

    await waitFor(() =>
      expect(
        urls.some((url) => url.includes('/admin/payments?') && url.includes('provider=paypal')),
      ).toBe(true),
    );
    expect(screen.getByRole('link', { name: /Export CSV/ })).toHaveAttribute(
      'href',
      '/api/v1/admin/payments/export.csv?provider=paypal',
    );
  });

  it('filters by date range', async () => {
    const user = userEvent.setup();
    const urls = serveDashboard();
    renderWithProviders(<AdminPaymentsPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    await user.type(screen.getByLabelText('From'), '2026-01-01');

    await waitFor(() => expect(urls.some((url) => url.includes('from=2026-01-01'))).toBe(true));
  });

  it('clears the filters again', async () => {
    const user = userEvent.setup();
    serveDashboard();
    renderWithProviders(<AdminPaymentsPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    await user.selectOptions(screen.getByLabelText('Status'), 'failed');
    await user.click(await screen.findByRole('button', { name: 'Clear filters' }));

    expect(screen.getByLabelText('Status')).toHaveValue('');
    expect(screen.getByRole('link', { name: /Export CSV/ })).toHaveAttribute(
      'href',
      '/api/v1/admin/payments/export.csv',
    );
  });

  it('asks the server to reorder when a column header is clicked', async () => {
    const user = userEvent.setup();
    const urls = serveDashboard();
    renderWithProviders(<AdminPaymentsPage />);

    await screen.findByRole('table', { name: /1 payment/ });
    await user.click(screen.getByRole('button', { name: /Total/ }));

    await waitFor(() =>
      expect(urls.some((url) => url.includes('ordering=amount_cents'))).toBe(true),
    );
  });

  it('shows an empty state when nothing matches', async () => {
    serveDashboard([]);
    renderWithProviders(<AdminPaymentsPage />);
    expect(await screen.findByText('No payments match these filters')).toBeInTheDocument();
  });
});
