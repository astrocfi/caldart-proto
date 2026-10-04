import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { Paginated, RenewalAttempt, RenewalMandate, ReportColumn } from '@/portal/api/types';
import { RenewalsPage } from './RenewalsPage';

const ACTIVE: RenewalMandate = {
  id: 12,
  user_id: 34,
  user_name: 'Maria Alvarez',
  user_email: 'maria@example.org',
  plan: 'annual',
  plan_name: 'Annual',
  kind: 'renewal',
  cadence: 'yearly',
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

const CONTRIBUTION_ONLY: RenewalMandate = {
  ...ACTIVE,
  id: 15,
  user_id: 37,
  user_name: 'Dana Field',
  user_email: 'dana@example.org',
  plan: null,
  plan_name: null,
  kind: 'contribution',
  cadence: 'monthly',
  contribution_cents: 5000,
  amount_cents: 5000,
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

/** The renewals report's registry, as `GET /reports/renewals/columns` answers it. */
const COLUMNS: ReportColumn[] = [
  { key: 'name', label: 'Member', default: true },
  { key: 'email', label: 'Email', default: true },
  { key: 'kind', label: 'Kind', default: true },
  { key: 'cadence', label: 'Cadence', default: false },
  { key: 'plan', label: 'Plan', default: true },
  { key: 'amount', label: 'Next charge', default: true },
  { key: 'next_charge_on', label: 'Due', default: true },
  { key: 'method', label: 'Method', default: true },
  { key: 'status', label: 'Status', default: true },
  { key: 'failures', label: 'Failed charges', default: false },
  { key: 'started_on', label: 'Started', default: false },
];

/** The registry the table and the chooser read, served for every test. */
beforeEach(() => {
  server.use(http.get(`${API}/reports/renewals/columns`, () => HttpResponse.json(COLUMNS)));
});

function page<Row>(rows: Row[], count = rows.length): Paginated<Row> {
  return { count, next: null, previous: null, results: rows };
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
    expect(row.getByText('03/14/2027')).toBeInTheDocument();
  });

  it('names a mandate with no plan a recurring donation, with its cadence', async () => {
    server.use(...renewalHandlers([CONTRIBUTION_ONLY], [], record()));
    renderWithProviders(<RenewalsPage />);

    const row = within(await screen.findByRole('row', { name: /Dana Field/ }));
    expect(row.getByText('Recurring donation')).toHaveTextContent('Recurring donation · Monthly');
  });

  it('names a renewal by its kind', async () => {
    server.use(...renewalHandlers([ACTIVE], [], record()));
    renderWithProviders(<RenewalsPage />);

    const row = within(await screen.findByRole('row', { name: /Maria Alvarez/ }));
    expect(row.getByText('Automatic renewal')).toBeInTheDocument();
  });

  it('shows why a paused mandate stopped', async () => {
    server.use(...renewalHandlers([PAUSED], [], record()));
    renderWithProviders(<RenewalsPage />);

    const row = within(await screen.findByRole('row', { name: /Ben Ortiz/ }));
    expect(row.getByText('Your card was declined')).toBeInTheDocument();
  });

  it('says what turning a mandate off does, and for whom', async () => {
    const seen = record();
    server.use(...renewalHandlers([PAUSED], [], seen));
    renderWithProviders(<RenewalsPage />);

    const row = within(await screen.findByRole('row', { name: /Ben Ortiz/ }));
    await userEvent.click(
      row.getByRole('button', { name: 'Turn off automatic renewal for Ben Ortiz' }),
    );

    expect(row.getByRole('region', { name: 'Turn off' })).toHaveTextContent(/for Ben Ortiz\?/);
  });

  it('turns a mandate off once the administrator confirms', async () => {
    const seen = record();
    server.use(...renewalHandlers([PAUSED], [], seen));
    renderWithProviders(<RenewalsPage />);

    const row = within(await screen.findByRole('row', { name: /Ben Ortiz/ }));
    await userEvent.click(
      row.getByRole('button', { name: 'Turn off automatic renewal for Ben Ortiz' }),
    );
    expect(seen.canceled).toEqual([]);

    await userEvent.click(row.getByRole('button', { name: 'Turn it off' }));

    await expect.poll(() => seen.canceled).toEqual([13]);
  });

  it('names the wording by kind when a contribution-only mandate is turned off', async () => {
    const seen = record();
    server.use(...renewalHandlers([CONTRIBUTION_ONLY], [], seen));
    renderWithProviders(<RenewalsPage />);

    const row = within(await screen.findByRole('row', { name: /Dana Field/ }));
    await userEvent.click(
      row.getByRole('button', {
        name: 'Turn off recurring donation for Dana Field',
      }),
    );
    await userEvent.click(row.getByRole('button', { name: 'Turn it off' }));

    expect(
      await screen.findByText('Recurring donation is off for Dana Field.'),
    ).toBeInTheDocument();
  });

  it('offers no way to turn off a mandate that is already off', async () => {
    server.use(...renewalHandlers([CANCELED], [], record()));
    renderWithProviders(<RenewalsPage />);

    const row = within(await screen.findByRole('row', { name: /Iris Kwan/ }));
    expect(row.queryByRole('button', { name: /^Turn off/ })).not.toBeInTheDocument();
  });

  it('narrows the mandates to one kind', async () => {
    const seen = record();
    server.use(...renewalHandlers([ACTIVE], [], seen));
    renderWithProviders(<RenewalsPage />);
    await screen.findByRole('row', { name: /Maria Alvarez/ });

    await userEvent.selectOptions(screen.getByLabelText('Type'), 'contribution');

    await expect.poll(() => seen.mandateQueries.at(-1)?.get('kind')).toBe('contribution');
  });

  it('narrows the mandates to one status', async () => {
    const seen = record();
    server.use(...renewalHandlers([ACTIVE], [], seen));
    renderWithProviders(<RenewalsPage />);
    await screen.findByRole('row', { name: /Maria Alvarez/ });

    await userEvent.selectOptions(screen.getByLabelText('Status'), 'paused');

    await expect.poll(() => seen.mandateQueries.at(-1)?.get('status')).toBe('paused');
  });

  it('lists a failed attempt with the reason the provider gave', async () => {
    server.use(...renewalHandlers([], [REFUSED], record()));
    renderWithProviders(<RenewalsPage />);

    const row = within(await screen.findByRole('row', { name: /03\/14\/2026/ }));
    expect(row.getByText('Failed')).toBeInTheDocument();
    expect(row.getByText('Your card was declined')).toBeInTheDocument();
  });

  it('tells the administrator when a mandate refuses to be turned off', async () => {
    server.use(
      http.delete(`${API}/admin/renewals/:id`, () =>
        HttpResponse.json({ detail: 'That renewal is already off.' }, { status: 400 }),
      ),
      ...renewalHandlers([PAUSED], [], record()),
    );
    renderWithProviders(<RenewalsPage />);

    const row = within(await screen.findByRole('row', { name: /Ben Ortiz/ }));
    await userEvent.click(
      row.getByRole('button', {
        name: 'Turn off automatic renewal for Ben Ortiz',
      }),
    );
    await userEvent.click(row.getByRole('button', { name: 'Turn it off' }));

    expect(await screen.findByText('That renewal is already off.')).toBeInTheDocument();
    expect(row.getByRole('button', { name: 'Turn it off' })).toBeInTheDocument();
  });

  it('counts every mandate the server has, not only the page on screen', async () => {
    const seen = record();
    server.use(
      http.get(`${API}/admin/renewals/attempts`, () => HttpResponse.json(page([]))),
      http.get(`${API}/admin/renewals`, ({ request }) => {
        seen.mandateQueries.push(new URL(request.url).searchParams);
        return HttpResponse.json(page([ACTIVE], 180));
      }),
    );
    renderWithProviders(<RenewalsPage />);

    expect(await screen.findByText('180 renewals')).toBeInTheDocument();

    const pager = within(screen.getByRole('navigation', { name: 'Renewal pages' }));
    expect(pager.getByText('Showing 1–50 of 180')).toBeInTheDocument();
    await userEvent.click(pager.getByRole('button', { name: 'Next' }));

    await expect.poll(() => seen.mandateQueries.at(-1)?.get('page')).toBe('2');
  });

  it('offers no pager when one page holds every mandate', async () => {
    server.use(...renewalHandlers([ACTIVE], [], record()));
    renderWithProviders(<RenewalsPage />);
    await screen.findByRole('row', { name: /Maria Alvarez/ });

    expect(screen.queryByRole('navigation', { name: 'Renewal pages' })).not.toBeInTheDocument();
  });

  it('pages the attempts by the count the server reports', async () => {
    const seen = record();
    server.use(
      http.get(`${API}/admin/renewals/attempts`, ({ request }) => {
        seen.attemptQueries.push(new URL(request.url).searchParams);
        return HttpResponse.json(page([REFUSED], 120));
      }),
      http.get(`${API}/admin/renewals`, () => HttpResponse.json(page([]))),
    );
    renderWithProviders(<RenewalsPage />);

    expect(await screen.findByText('120 attempts')).toBeInTheDocument();

    const pager = within(screen.getByRole('navigation', { name: 'Renewal charge pages' }));
    await userEvent.click(pager.getByRole('button', { name: 'Next' }));

    await expect.poll(() => seen.attemptQueries.at(-1)?.get('page')).toBe('2');
  });

  it('keeps the renewals on their page while the charges page on', async () => {
    const seen = record();
    server.use(
      http.get(`${API}/admin/renewals/attempts`, ({ request }) => {
        seen.attemptQueries.push(new URL(request.url).searchParams);
        return HttpResponse.json(page([REFUSED], 120));
      }),
      http.get(`${API}/admin/renewals`, ({ request }) => {
        seen.mandateQueries.push(new URL(request.url).searchParams);
        return HttpResponse.json(page([ACTIVE], 180));
      }),
    );
    renderWithProviders(<RenewalsPage />);
    expect(await screen.findByText('180 renewals')).toBeInTheDocument();

    const renewals = within(screen.getByRole('navigation', { name: 'Renewal pages' }));
    await userEvent.click(renewals.getByRole('button', { name: 'Next' }));
    await expect.poll(() => seen.mandateQueries.at(-1)?.get('page')).toBe('2');
    const charges = within(screen.getByRole('navigation', { name: 'Renewal charge pages' }));
    await userEvent.click(charges.getByRole('button', { name: 'Next' }));
    await expect.poll(() => seen.attemptQueries.at(-1)?.get('page')).toBe('2');

    expect(seen.mandateQueries.at(-1)?.get('page')).toBe('2');
  });

  it('says so when the mandates cannot be loaded', async () => {
    server.use(
      http.get(`${API}/admin/renewals/attempts`, () => HttpResponse.json(page([]))),
      http.get(`${API}/admin/renewals`, () => new HttpResponse(null, { status: 500 })),
    );
    renderWithProviders(<RenewalsPage />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      "The renewals didn't load. Try again in a moment.",
    );
  });

  it('narrows the attempts to one outcome', async () => {
    const seen = record();
    server.use(...renewalHandlers([], [REFUSED], seen));
    renderWithProviders(<RenewalsPage />);
    await screen.findByRole('row', { name: /03\/14\/2026/ });

    await userEvent.selectOptions(screen.getByLabelText('Outcome'), 'succeeded');

    await expect.poll(() => seen.attemptQueries.at(-1)?.get('outcome')).toBe('succeeded');
  });

  it('keeps the filters in the address, so a filtered tab can be linked', async () => {
    const seen = record();
    server.use(...renewalHandlers([ACTIVE], [], seen));
    renderWithProviders(<RenewalsPage />, {
      route: '/admin/payments/renewals?status=paused&search=ortiz',
    });
    await screen.findByRole('row', { name: /Maria Alvarez/ });

    await expect
      .poll(() => [
        seen.mandateQueries.at(-1)?.get('status'),
        seen.mandateQueries.at(-1)?.get('search'),
      ])
      .toEqual(['paused', 'ortiz']);
  });

  it('points the exports at the renewals report with the filters and columns chosen', async () => {
    server.use(...renewalHandlers([ACTIVE], [], record()));
    renderWithProviders(<RenewalsPage />, { route: '/admin/payments/renewals?kind=both' });
    await screen.findByRole('row', { name: /Maria Alvarez/ });

    expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute(
      'href',
      '/api/v1/reports/renewals/export.csv?kind=both' +
        '&columns=name%2Cemail%2Ckind%2Cplan%2Camount%2Cnext_charge_on%2Cmethod%2Cstatus',
    );
  });

  it('adds a chosen column to the table', async () => {
    const user = userEvent.setup();
    server.use(...renewalHandlers([PAUSED], [], record()));
    renderWithProviders(<RenewalsPage />);
    await screen.findByRole('row', { name: /Ben Ortiz/ });

    await user.click(screen.getByRole('button', { name: 'Columns' }));
    await user.click(screen.getByRole('checkbox', { name: 'Failed charges' }));

    expect(screen.getByRole('columnheader', { name: /Failed charges/ })).toBeInTheDocument();
  });

  it('offers to reset the filters from an empty list', async () => {
    const user = userEvent.setup();
    const seen = record();
    server.use(...renewalHandlers([], [], seen));
    renderWithProviders(<RenewalsPage />, { route: '/admin/payments/renewals?status=paused' });

    await screen.findByText('No renewals match');
    await user.click(screen.getAllByRole('button', { name: 'Reset filters' }).at(-2)!);

    await expect.poll(() => seen.mandateQueries.at(-1)?.get('status')).toBeNull();
  });
});
