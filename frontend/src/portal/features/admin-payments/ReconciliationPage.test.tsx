import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { ReconciliationRow } from '@/portal/api/types';
import { ReconciliationPage } from './ReconciliationPage';
import { reconciliationExportUrl, reconciliationPeriodLabel } from './reports-api';

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
    expect(reconciliationPeriodLabel('2026-01', 'month')).toBe('January 2026');
  });

  it('leaves a year as it is', () => {
    expect(reconciliationPeriodLabel('2026', 'year')).toBe('2026');
  });

  it('names a provider the way the rest of the portal does', () => {
    expect(reconciliationPeriodLabel('stripe', 'provider')).toBe('Stripe');
  });
});

describe('reconciliationExportUrl', () => {
  it('carries the range, the provider and the grouping', () => {
    expect(
      reconciliationExportUrl(
        { from: '2026-01-01', to: '2026-03-31', provider: 'paypal' },
        'year',
        'csv',
      ),
    ).toBe(
      `${API}/admin/payments/reconciliation/export.csv` +
        '?group=year&from=2026-01-01&to=2026-03-31&provider=paypal',
    );
  });

  it('asks for the PDF with no filters when none are set', () => {
    expect(reconciliationExportUrl({ from: '', to: '', provider: '' }, 'month', 'pdf')).toBe(
      `${API}/admin/payments/reconciliation/export.pdf?group=month`,
    );
  });
});

describe('ReconciliationPage', () => {
  it('shows a period with its gross, fees, net and what is still unmatched', async () => {
    server.use(reconciliationHandler([JANUARY], []));
    renderWithProviders(<ReconciliationPage />);

    const row = within(await screen.findByRole('row', { name: /January 2026/ }));
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

    await userEvent.click(screen.getByRole('button', { name: 'Provider' }));

    await expect
      .poll(() => seen.map((params) => params.get('group')))
      .toEqual(['month', 'provider']);
  });

  it('narrows the range and the exports together', async () => {
    const seen: URLSearchParams[] = [];
    server.use(reconciliationHandler([JANUARY], seen));
    renderWithProviders(<ReconciliationPage />);
    await screen.findByRole('row', { name: /January 2026/ });

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
});
