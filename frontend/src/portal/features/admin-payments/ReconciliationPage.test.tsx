import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { ReconciliationRow } from '@/portal/api/types';
import { ReconciliationPage } from './ReconciliationPage';
import { reconciliationPeriodLabel } from './reports-api';

const JANUARY: ReconciliationRow = {
  period: '2026-01',
  count: 24,
  gross_cents: 148000,
  fee_cents: 4620,
  net_cents: 143380,
  refunded_cents: 2500,
  net_after_refunds_cents: 140880,
  reconciled_count: 22,
  unreconciled_count: 2,
};

const STRIPE: ReconciliationRow = { ...JANUARY, period: 'stripe' };

/** Answer the reconciliation call, recording the query it was asked with. */
function reconciliationHandler(rows: ReconciliationRow[], seen: URLSearchParams[]) {
  return http.get(`${API}/admin/payments/reconciliation`, ({ request }) => {
    seen.push(new URL(request.url).searchParams);
    return HttpResponse.json(rows);
  });
}

describe('reconciliationPeriodLabel', () => {
  it('spells a month out', () => {
    expect(reconciliationPeriodLabel('2026-01', 'month')).toBe('Jan 2026');
  });

  it('leaves a year as it is', () => {
    expect(reconciliationPeriodLabel('2026', 'year')).toBe('2026');
  });

  it('names a provider the way the rest of the portal does', () => {
    expect(reconciliationPeriodLabel('stripe', 'provider')).toBe('Stripe');
  });
});

describe('ReconciliationPage', () => {
  it('shows a period with its gross, fees, net and what is still unmatched', async () => {
    server.use(reconciliationHandler([JANUARY], []));
    renderWithProviders(<ReconciliationPage />);

    const row = within(await screen.findByRole('row', { name: /Jan 2026/ }));
    expect(row.getByText('$1,480.00')).toBeInTheDocument();
    expect(row.getByText('$46.20')).toBeInTheDocument();
    expect(row.getByText('$1,408.80')).toBeInTheDocument();
    expect(row.getByText('22 of 24')).toBeInTheDocument();
  });

  it('asks the server to group by provider when the provider grouping is chosen', async () => {
    const seen: URLSearchParams[] = [];
    server.use(reconciliationHandler([STRIPE], seen));
    renderWithProviders(<ReconciliationPage />);
    await screen.findByRole('row', { name: /stripe/i });

    await userEvent.selectOptions(screen.getByLabelText('Rows'), 'provider');

    await expect.poll(() => seen.map((params) => params.get('group'))).toEqual([null, 'provider']);
  });

  it('reads its filters from the address, so a grouping can be linked', async () => {
    const seen: URLSearchParams[] = [];
    server.use(reconciliationHandler([JANUARY], seen));
    renderWithProviders(<ReconciliationPage />, {
      route: '/admin/payments/reconciliation?group=year&provider=paypal',
    });

    expect(await screen.findByRole('table', { name: 'Takings by year' })).toBeInTheDocument();
    expect(seen[0]!.get('provider')).toBe('paypal');
  });

  it('points the exports at the reconciliation report with the filters on screen', async () => {
    server.use(reconciliationHandler([JANUARY], []));
    renderWithProviders(<ReconciliationPage />, {
      route: '/admin/payments/reconciliation?group=month&to=2026-03-31',
    });
    await screen.findByRole('row', { name: /Jan 2026/ });

    expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
      'href',
      `${API}/reports/reconciliation/export.csv?to=2026-03-31&group=month`,
    );
    expect(screen.getByRole('link', { name: 'Export PDF' })).toHaveAttribute(
      'href',
      `${API}/reports/reconciliation/export.pdf?to=2026-03-31&group=month`,
    );
  });

  it('narrows the range and the exports together', async () => {
    const seen: URLSearchParams[] = [];
    server.use(reconciliationHandler([JANUARY], seen));
    renderWithProviders(<ReconciliationPage />);
    await screen.findByRole('row', { name: /Jan 2026/ });

    await userEvent.type(screen.getByLabelText('From'), '2026-01-01');

    await expect.poll(() => seen.at(-1)?.get('from')).toBe('2026-01-01');
    expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
      'href',
      expect.stringContaining('from=2026-01-01'),
    );
  });

  it('says so when the range holds no money at all', async () => {
    server.use(reconciliationHandler([], []));
    renderWithProviders(<ReconciliationPage />);

    expect(await screen.findByText('Nothing was taken in this range')).toBeInTheDocument();
  });

  it('shows a failed call as a failure, not as an empty period', async () => {
    server.use(
      http.get(
        `${API}/admin/payments/reconciliation`,
        () => new HttpResponse(null, { status: 500 }),
      ),
    );
    renderWithProviders(<ReconciliationPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The reconciliation could not be loaded.',
    );
  });
});
