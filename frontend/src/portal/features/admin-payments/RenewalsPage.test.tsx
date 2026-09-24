import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { Paginated, RenewalAttempt, RenewalMandate } from '@/portal/api/types';
import { RenewalsPage } from './RenewalsPage';

const ACTIVE: RenewalMandate = {
  id: 12,
  user_id: 34,
  user_name: 'Maria Alvarez',
  user_email: 'maria@example.org',
  plan: 'annual',
  plan_name: 'Annual',
  contribution_cents: 2500,
  amount_cents: 7000,
  provider: 'stripe',
  method_label: 'Visa ending 4242, expires 03/2028',
  method_brand: 'visa',
  method_last4: '4242',
  method_exp_month: 3,
  method_exp_year: 2028,
  status: 'active',
  failure_count: 0,
  next_charge_on: '2027-03-14',
  last_error: '',
  last_charged_at: '2026-03-14T18:22:05Z',
  canceled_at: null,
  created_at: '2025-03-14T18:21:58Z',
};

const PAUSED: RenewalMandate = {
  ...ACTIVE,
  id: 13,
  user_id: 35,
  user_name: 'Ben Ortiz',
  user_email: 'ben@example.org',
  method_last4: '0002',
  status: 'paused',
  failure_count: 4,
  next_charge_on: null,
  last_error: 'Your card was declined',
  last_charged_at: null,
};

const CANCELED: RenewalMandate = {
  ...ACTIVE,
  id: 14,
  user_id: 36,
  user_name: 'Iris Kwan',
  user_email: 'iris@example.org',
  status: 'canceled',
  next_charge_on: null,
  canceled_at: '2026-05-01T09:00:00Z',
};

const REFUSED: RenewalAttempt = {
  id: 87,
  mandate_id: 13,
  membership_id: 455,
  payment_id: null,
  user_id: 35,
  user_name: 'Ben Ortiz',
  scheduled_on: '2026-03-14',
  outcome: 'failed',
  error: 'Your card was declined',
  noticed_at: '2026-02-28T06:30:11Z',
  attempted_at: '2026-03-14T06:30:09Z',
  result_emailed_at: '2026-03-14T06:30:12Z',
  created_at: '2026-02-28T06:30:11Z',
};

function page<Row>(rows: Row[]): Paginated<Row> {
  return { count: rows.length, next: null, previous: null, results: rows };
}

interface Recorded {
  mandateQueries: URLSearchParams[];
  attemptQueries: URLSearchParams[];
  canceled: number[];
}

/** The three calls the tab makes, with what each was asked. */
function renewalHandlers(mandates: RenewalMandate[], attempts: RenewalAttempt[], seen: Recorded) {
  return [
    http.get(`${API}/admin/renewals/attempts`, ({ request }) => {
      seen.attemptQueries.push(new URL(request.url).searchParams);
      return HttpResponse.json(page(attempts));
    }),
    http.get(`${API}/admin/renewals`, ({ request }) => {
      seen.mandateQueries.push(new URL(request.url).searchParams);
      return HttpResponse.json(page(mandates));
    }),
    http.delete(`${API}/admin/renewals/:id`, ({ params }) => {
      seen.canceled.push(Number(params.id));
      return new HttpResponse(null, { status: 204 });
    }),
  ];
}

function record(): Recorded {
  return { mandateQueries: [], attemptQueries: [], canceled: [] };
}

describe('RenewalsPage', () => {
  it('shows a mandate with its method, amount and next charge', async () => {
    server.use(...renewalHandlers([ACTIVE], [], record()));
    renderWithProviders(<RenewalsPage />);

    const row = within(await screen.findByRole('row', { name: /Maria Alvarez/ }));
    expect(row.getByText('Visa ending 4242, expires 03/2028')).toBeInTheDocument();
    expect(row.getByText('$70.00')).toBeInTheDocument();
    expect(row.getByText('2027/03/14')).toBeInTheDocument();
  });

  it('shows why a paused mandate stopped', async () => {
    server.use(...renewalHandlers([PAUSED], [], record()));
    renderWithProviders(<RenewalsPage />);

    const row = within(await screen.findByRole('row', { name: /Ben Ortiz/ }));
    expect(row.getByText('Your card was declined')).toBeInTheDocument();
  });

  it('turns a mandate off once the administrator confirms', async () => {
    const seen = record();
    server.use(...renewalHandlers([PAUSED], [], seen));
    renderWithProviders(<RenewalsPage />);

    const row = within(await screen.findByRole('row', { name: /Ben Ortiz/ }));
    await userEvent.click(row.getByRole('button', { name: 'Turn off' }));
    expect(seen.canceled).toEqual([]);

    await userEvent.click(row.getByRole('button', { name: 'Yes, turn it off' }));

    await expect.poll(() => seen.canceled).toEqual([13]);
  });

  it('offers no way to turn off a mandate that is already off', async () => {
    server.use(...renewalHandlers([CANCELED], [], record()));
    renderWithProviders(<RenewalsPage />);

    const row = within(await screen.findByRole('row', { name: /Iris Kwan/ }));
    expect(row.queryByRole('button', { name: 'Turn off' })).not.toBeInTheDocument();
  });

  it('narrows the mandates to one status', async () => {
    const seen = record();
    server.use(...renewalHandlers([ACTIVE], [], seen));
    renderWithProviders(<RenewalsPage />);
    await screen.findByRole('row', { name: /Maria Alvarez/ });

    await userEvent.selectOptions(screen.getByLabelText('Renewal status'), 'paused');

    await expect.poll(() => seen.mandateQueries.at(-1)?.get('status')).toBe('paused');
  });

  it('lists a refused attempt with the reason the provider gave', async () => {
    server.use(...renewalHandlers([], [REFUSED], record()));
    renderWithProviders(<RenewalsPage />);

    const row = within(await screen.findByRole('row', { name: /2026\/03\/14/ }));
    expect(row.getByText('Refused')).toBeInTheDocument();
    expect(row.getByText('Your card was declined')).toBeInTheDocument();
  });

  it('narrows the attempts to one outcome', async () => {
    const seen = record();
    server.use(...renewalHandlers([], [REFUSED], seen));
    renderWithProviders(<RenewalsPage />);
    await screen.findByRole('row', { name: /2026\/03\/14/ });

    await userEvent.selectOptions(screen.getByLabelText('Outcome'), 'succeeded');

    await expect.poll(() => seen.attemptQueries.at(-1)?.get('outcome')).toBe('succeeded');
  });
});
