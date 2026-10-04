import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { ReconciliationRow } from '@/portal/api/types';
import { API_BASE } from '@/portal/urlPrefix';
import { ReconciliationPage, unmatchedPaymentsUrl } from './ReconciliationPage';
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

const FEBRUARY: ReconciliationRow = {
  ...JANUARY,
  period: '2026-02',
  count: 4,
  gross_cents: 18000,
  fee_cents: 500,
  net_cents: 17500,
  refunded_cents: 0,
  net_after_refunds_cents: 17500,
  reconciled_count: 4,
  unreconciled_count: 0,
};

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

describe('unmatchedPaymentsUrl', () => {
  it('narrows the payment list to the month and to what is not reconciled', () => {
    expect(unmatchedPaymentsUrl(JANUARY, 'month', {})).toBe(
      '/admin/payments/list?from=2026-01-01&to=2026-01-31&reconciled=no',
    );
  });

  it('keeps the range on screen when it cuts into the period', () => {
    expect(unmatchedPaymentsUrl(JANUARY, 'month', { from: '2026-01-10', provider: 'paypal' })).toBe(
      '/admin/payments/list?from=2026-01-10&to=2026-01-31&provider=paypal&reconciled=no',
    );
  });

  it('spans the whole year for a year row', () => {
    expect(unmatchedPaymentsUrl({ ...JANUARY, period: '2025' }, 'year', {})).toBe(
      '/admin/payments/list?from=2025-01-01&to=2025-12-31&reconciled=no',
    );
  });

  it("names the row's provider over the range on screen for a provider row", () => {
    expect(unmatchedPaymentsUrl(STRIPE, 'provider', { to: '2026-03-31' })).toBe(
      '/admin/payments/list?to=2026-03-31&provider=stripe&reconciled=no',
    );
  });
});

describe('ReconciliationPage', () => {
  it('links a period not fully reconciled to the payments still waiting', async () => {
    server.use(reconciliationHandler([JANUARY], []));
    renderWithProviders(<ReconciliationPage />);

    expect(
      await screen.findByRole('link', { name: /^22 of 24 reconciled, Jan 2026/ }),
    ).toHaveAttribute('href', '/admin/payments/list?from=2026-01-01&to=2026-01-31&reconciled=no');
  });

  it('leaves a fully reconciled period as plain figures', async () => {
    server.use(reconciliationHandler([FEBRUARY], []));
    renderWithProviders(<ReconciliationPage />);

    const row = within(await screen.findByRole('row', { name: /Feb 2026/ }));
    expect(row.getByText('4 of 4')).not.toHaveAttribute('href');
  });

  it('lists the newest period first', async () => {
    server.use(reconciliationHandler([FEBRUARY, JANUARY], []));
    renderWithProviders(<ReconciliationPage />);
    await screen.findByRole('row', { name: /Jan 2026/ });

    const body = screen.getAllByRole('rowgroup')[1]!;
    expect(
      within(body)
        .getAllByRole('row')
        .map((row) => within(row).getAllByRole('rowheader')[0]?.textContent),
    ).toEqual(['Feb 2026', 'Jan 2026']);
  });

  it('adds every figure up in a totals row', async () => {
    server.use(reconciliationHandler([FEBRUARY, JANUARY], []));
    renderWithProviders(<ReconciliationPage />);

    const totals = within(await screen.findByRole('row', { name: /^Total/ }));
    expect(totals.getByText('$1,660.00')).toBeInTheDocument();
    expect(totals.getByText('26 of 28')).toBeInTheDocument();
  });

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

    expect(await screen.findByRole('table', { name: 'Money in by year' })).toBeInTheDocument();
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
      `${API_BASE}/reports/reconciliation/export.csv?to=2026-03-31&group=month`,
    );
    expect(screen.getByRole('link', { name: 'Export PDF' })).toHaveAttribute(
      'href',
      `${API_BASE}/reports/reconciliation/export.pdf?to=2026-03-31&group=month`,
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
      "The reconciliation didn't load. Try again in a moment.",
    );
  });
});
