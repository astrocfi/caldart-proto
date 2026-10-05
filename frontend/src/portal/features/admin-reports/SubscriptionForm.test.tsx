import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { API, makeSubscription, subscriptionHandlers } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { ReportColumn, ReportSubscription, ReportSummary } from '@/portal/api/types';
import { SubscriptionForm, storedFilters } from './SubscriptionForm';

const REPORTS: ReportSummary[] = [
  { slug: 'members', title: 'Members', choosable: true, periods: false },
  { slug: 'payments', title: 'Payments', choosable: true, periods: true },
  { slug: 'contributions', title: 'Contributions', choosable: false, periods: true },
];

const MEMBER_COLUMNS: ReportColumn[] = [
  { key: 'name', label: 'Name', default: true },
  { key: 'email', label: 'Email', default: true },
  { key: 'county', label: 'County', default: false },
];

/** Render the form over the three reports; every POST body lands in `bodies`. */
function renderForm(bodies: unknown[] = [], handleDone = vi.fn()) {
  server.use(
    ...subscriptionHandlers({ reports: REPORTS }),
    http.get(`${API}/reports/members/columns`, () => HttpResponse.json(MEMBER_COLUMNS)),
    http.post(`${API}/reports/subscriptions`, async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json(makeSubscription(), { status: 201 });
    }),
  );
  renderWithProviders(<SubscriptionForm onDone={handleDone} />);
  return handleDone;
}

/** Pick `title` in the Report box, once the reports have loaded. */
async function chooseReport(title: string): Promise<void> {
  await screen.findByRole('option', { name: title });
  await userEvent.selectOptions(screen.getByLabelText('Report'), title);
}

/** The form's own controls, outside the filter bar. */
function form(): HTMLElement {
  return screen.getByRole('form', { name: 'Email a report' });
}

describe('storedFilters', () => {
  it('drops a fixed contributions year, which the form no longer draws', () => {
    expect(
      storedFilters(
        makeSubscription({ report: 'contributions', filters: { year: '2024', period: '' } }),
      ),
    ).toEqual({ period: '' });
  });

  it('keeps every filter the form draws for the report', () => {
    expect(
      storedFilters(makeSubscription({ report: 'payments', filters: { period: 'last_month' } })),
    ).toEqual({ period: 'last_month' });
  });
});

describe('SubscriptionForm', () => {
  it('offers only the reports the caller may read', async () => {
    renderForm();

    await screen.findByRole('option', { name: 'Members' });
    const offered = within(screen.getByLabelText('Report'))
      .getAllByRole('option')
      .map((option) => option.textContent);
    expect(offered).toEqual(['Choose a report…', 'Members', 'Payments', 'Contributions']);
  });

  it('names each report as its tab does, not by the title its PDF carries', async () => {
    server.use(
      ...subscriptionHandlers({
        reports: [
          {
            slug: 'reconciliation',
            title: 'CalDART reconciliation',
            choosable: false,
            periods: true,
          },
        ],
      }),
    );
    const handleDone = vi.fn();
    renderWithProviders(<SubscriptionForm onDone={handleDone} />);

    expect(await screen.findByRole('option', { name: 'Reconciliation' })).toBeInTheDocument();
  });

  it('says why Save waits until a report is chosen', () => {
    renderForm();

    expect(
      within(form()).getByRole('button', { name: 'Add emailed report' }),
    ).toHaveAccessibleDescription('Choose a report first.');
  });

  it('drops the hint once a report is chosen', async () => {
    renderForm();

    await chooseReport('Members');

    expect(within(form()).queryByText('Choose a report first.')).not.toBeInTheDocument();
  });

  it('gives the contributions one Year control, this year or last year', async () => {
    renderForm();

    await chooseReport('Contributions');

    const bar = screen.getByRole('search', { name: 'Report filters' });
    const year = within(bar).getByLabelText('Year');
    expect(
      within(year)
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['This year', 'Last year']);
  });

  it('offers a period on the reconciliation, so a monthly email can cover last month', async () => {
    server.use(
      ...subscriptionHandlers({
        reports: [
          { slug: 'reconciliation', title: 'Reconciliation', choosable: false, periods: true },
        ],
      }),
    );
    const handleDone = vi.fn();
    renderWithProviders(<SubscriptionForm onDone={handleDone} />);

    await chooseReport('Reconciliation');

    const bar = screen.getByRole('search', { name: 'Report filters' });
    expect(within(bar).getByRole('option', { name: 'Last month' })).toBeInTheDocument();
  });

  it('offers the reconciliation its Period alone, with no fixed dates beside it', async () => {
    server.use(
      ...subscriptionHandlers({
        reports: [
          { slug: 'reconciliation', title: 'Reconciliation', choosable: false, periods: true },
        ],
      }),
    );
    const handleDone = vi.fn();
    renderWithProviders(<SubscriptionForm onDone={handleDone} />);

    await chooseReport('Reconciliation');

    const bar = screen.getByRole('search', { name: 'Report filters' });
    expect(within(bar).queryByLabelText('From')).not.toBeInTheDocument();
    expect(within(bar).queryByLabelText('To')).not.toBeInTheDocument();
  });

  it('draws no Reset filters button among the form of a subscription', async () => {
    renderForm();

    await chooseReport('Payments');

    const bar = screen.getByRole('search', { name: 'Report filters' });
    expect(within(bar).queryByRole('button', { name: 'Reset filters' })).not.toBeInTheDocument();
  });

  it("draws the chosen report's filters, the period included", async () => {
    renderForm();

    await chooseReport('Payments');

    const bar = screen.getByRole('search', { name: 'Report filters' });
    expect(within(bar).getByLabelText('Period')).toBeInTheDocument();
    expect(within(bar).getByLabelText('Status')).toBeInTheDocument();
  });

  it("offers the email log's purposes in its Purpose filter", async () => {
    server.use(
      ...subscriptionHandlers({
        reports: [
          ...REPORTS,
          { slug: 'emails', title: 'CalDART email log', choosable: true, periods: false },
        ],
      }),
    );
    const handleDone = vi.fn();
    renderWithProviders(<SubscriptionForm onDone={handleDone} />);

    await chooseReport('Sent emails');

    const bar = screen.getByRole('search', { name: 'Report filters' });
    const offered = within(bar)
      .getAllByRole('option')
      .filter((option) => option.closest('select') === within(bar).getByLabelText('Purpose'))
      .map((option) => option.textContent);
    expect(offered).toEqual(['Any purpose', 'Receipt', 'Password reset']);
  });

  it('never asks for the email purposes unless the emails report is chosen', async () => {
    let purposesRequested = false;
    server.use(
      ...subscriptionHandlers({ reports: REPORTS }),
      http.get(`${API}/reports/members/columns`, () => HttpResponse.json(MEMBER_COLUMNS)),
      http.get(`${API}/system/emails/purposes`, () => {
        purposesRequested = true;
        return HttpResponse.json([]);
      }),
    );
    const handleDone = vi.fn();
    renderWithProviders(<SubscriptionForm onDone={handleDone} />);

    await chooseReport('Members');
    await screen.findByRole('button', { name: 'Columns' });

    expect(purposesRequested).toBe(false);
  });

  it('offers the column chooser for a report whose columns can be chosen', async () => {
    renderForm();

    await chooseReport('Members');

    expect(await screen.findByRole('button', { name: 'Columns' })).toBeInTheDocument();
  });

  it('offers no column chooser for a fixed report', async () => {
    renderForm();

    await chooseReport('Contributions');

    expect(screen.queryByRole('button', { name: 'Columns' })).not.toBeInTheDocument();
  });

  it('asks for the weekday of a weekly schedule only', async () => {
    renderForm();
    await chooseReport('Members');

    expect(within(form()).queryByLabelText('Day')).not.toBeInTheDocument();
    await userEvent.selectOptions(within(form()).getByLabelText('Schedule'), 'Weekly');

    expect(within(form()).getByLabelText('Day')).toHaveValue('0');
  });

  it('posts the report, its filters, the formats, the schedule and the address', async () => {
    const bodies: unknown[] = [];
    const onDone = renderForm(bodies);
    await chooseReport('Payments');

    await userEvent.selectOptions(screen.getByLabelText('Period'), 'This year');
    await userEvent.click(within(form()).getByLabelText('CSV'));
    await userEvent.selectOptions(within(form()).getByLabelText('Schedule'), 'Quarterly');
    await userEvent.type(within(form()).getByLabelText(/^Recipient email/), 'tessa@example.org');
    await userEvent.click(within(form()).getByRole('button', { name: 'Add emailed report' }));

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(bodies).toEqual([
      {
        report: 'payments',
        recipient_email: 'tessa@example.org',
        filters: { period: 'this_year' },
        columns: [],
        formats: 'csv',
        cadence: 'quarterly',
        weekday: 0,
        confirmed: false,
      },
    ]);
  });

  it('sends the chosen columns once they have been changed', async () => {
    const bodies: unknown[] = [];
    renderForm(bodies);
    await chooseReport('Members');

    await userEvent.click(await screen.findByRole('button', { name: 'Columns' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'County' }));
    await userEvent.type(within(form()).getByLabelText(/^Recipient email/), 'ada@example.org');
    await userEvent.click(within(form()).getByRole('button', { name: 'Add emailed report' }));

    await vi.waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toMatchObject({ columns: ['name', 'email', 'county'] });
  });

  it('sends the weekday of a weekly schedule', async () => {
    const bodies: unknown[] = [];
    renderForm(bodies);
    await chooseReport('Members');

    await userEvent.selectOptions(within(form()).getByLabelText('Schedule'), 'Weekly');
    await userEvent.selectOptions(within(form()).getByLabelText('Day'), 'Thursday');
    await userEvent.type(within(form()).getByLabelText(/^Recipient email/), 'ada@example.org');
    await userEvent.click(within(form()).getByRole('button', { name: 'Add emailed report' }));

    await vi.waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toMatchObject({ cadence: 'weekly', weekday: 3 });
  });

  it('shows a refused recipient under the address', async () => {
    renderForm();
    server.use(
      http.post(`${API}/reports/subscriptions`, () =>
        HttpResponse.json(
          { recipient_email: ['Tessa Treasurer does not hold a role that may read this report.'] },
          { status: 400 },
        ),
      ),
    );
    await chooseReport('Members');

    await userEvent.type(within(form()).getByLabelText(/^Recipient email/), 'tessa@example.org');
    await userEvent.click(within(form()).getByRole('button', { name: 'Add emailed report' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Tessa Treasurer does not hold a role that may read this report.',
    );
    expect(within(form()).getByLabelText(/^Recipient email/)).toHaveAttribute(
      'aria-invalid',
      'true',
    );
  });

  it('asks for confirmation of an address outside CalDART, and sends it', async () => {
    const bodies: { confirmed?: boolean }[] = [];
    renderForm();
    server.use(
      http.post(`${API}/reports/subscriptions`, async ({ request }) => {
        const body = (await request.json()) as { confirmed?: boolean };
        bodies.push(body);
        if (body.confirmed === true) {
          return HttpResponse.json(makeSubscription(), { status: 201 });
        }
        return HttpResponse.json(
          { confirmed: ['Check the box to confirm this address may receive this report.'] },
          { status: 400 },
        );
      }),
    );
    await chooseReport('Members');

    const outside = 'This address is outside CalDART and may receive this report';
    expect(within(form()).queryByLabelText(outside)).not.toBeInTheDocument();
    await userEvent.type(within(form()).getByLabelText(/^Recipient email/), 'board@example.org');
    await userEvent.click(within(form()).getByRole('button', { name: 'Add emailed report' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Check the box to confirm this address may receive this report.',
    );
    await userEvent.click(within(form()).getByLabelText(outside));
    await userEvent.click(within(form()).getByRole('button', { name: 'Add emailed report' }));

    await vi.waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]?.confirmed).toBe(true);
  });

  it('shows a refused filter by its label', async () => {
    renderForm();
    server.use(
      http.post(`${API}/reports/subscriptions`, () =>
        HttpResponse.json({ filters: { period: ['Choose a valid period.'] } }, { status: 400 }),
      ),
    );
    await chooseReport('Payments');

    await userEvent.type(within(form()).getByLabelText(/^Recipient email/), 'ada@example.org');
    await userEvent.click(within(form()).getByRole('button', { name: 'Add emailed report' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Period: Choose a valid period.');
  });

  it('asks for a report before it saves', async () => {
    const bodies: unknown[] = [];
    renderForm(bodies);
    await screen.findByRole('option', { name: 'Members' });

    expect(within(form()).getByRole('button', { name: 'Add emailed report' })).toBeDisabled();
    expect(bodies).toEqual([]);
  });

  it('closes on Cancel without saving', async () => {
    const bodies: unknown[] = [];
    const onDone = renderForm(bodies);
    await chooseReport('Members');

    await userEvent.click(within(form()).getByRole('button', { name: 'Cancel' }));

    expect(onDone).toHaveBeenCalled();
    expect(bodies).toEqual([]);
  });
});

/** A weekly subscription to the member report, filtered and with two columns chosen. */
const STORED = makeSubscription({
  id: 5,
  report: 'members',
  report_title: 'CalDART membership report',
  recipient_name: 'Ada Admin',
  recipient_email: 'ada@example.org',
  filters: { kind: 'friend', expiring_within: '30' },
  columns: ['name', 'county'],
  formats: 'both',
  cadence: 'weekly',
  weekday: 3,
});

/** Render the form editing `subscription`; every PATCH body lands in `bodies`. */
function renderEdit(
  subscription: ReportSubscription = STORED,
  bodies: unknown[] = [],
  handleDone = vi.fn(),
) {
  server.use(
    http.patch(`${API}/reports/subscriptions/${subscription.id}`, async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json(subscription);
    }),
    ...subscriptionHandlers({ reports: REPORTS, subscriptions: [subscription] }),
    http.get(`${API}/reports/members/columns`, () => HttpResponse.json(MEMBER_COLUMNS)),
  );
  renderWithProviders(<SubscriptionForm subscription={subscription} onDone={handleDone} />);
  return handleDone;
}

/** The edit form's own controls, outside the filter bar. */
function editForm(): HTMLElement {
  return screen.getByRole('form', { name: 'Edit emailed report' });
}

describe('SubscriptionForm editing a subscription', () => {
  it('is headed Edit emailed report', () => {
    renderEdit();

    expect(screen.getByRole('heading', { name: 'Edit emailed report' })).toBeInTheDocument();
  });

  it('shows the report as fixed text, by its tab name, rather than a choice', () => {
    renderEdit();

    expect(screen.getByRole('group', { name: 'Report' })).toHaveTextContent(/^Report\s*Members$/);
    expect(screen.queryByRole('combobox', { name: 'Report' })).not.toBeInTheDocument();
  });

  it('shows the recipient as fixed text rather than an address box', () => {
    renderEdit();

    expect(within(editForm()).getByRole('group', { name: 'Recipient' })).toHaveTextContent(
      'Ada Admin',
    );
    expect(within(editForm()).queryByLabelText(/^Recipient email/)).not.toBeInTheDocument();
  });

  it("fills the report's filters from the subscription", () => {
    renderEdit();

    const bar = screen.getByRole('search', { name: 'Report filters' });
    expect(within(bar).getByLabelText('Kind')).toHaveValue('friend');
    expect(within(bar).getByLabelText('Expiring within (days)')).toHaveValue('30');
  });

  it('checks the stored columns in the chooser', async () => {
    renderEdit();

    await userEvent.click(await screen.findByRole('button', { name: 'Columns' }));

    const checked = MEMBER_COLUMNS.filter(
      (column) => screen.getByRole<HTMLInputElement>('checkbox', { name: column.label }).checked,
    ).map((column) => column.label);
    expect(checked).toEqual(['Name', 'County']);
  });

  it('fills the formats, the schedule and the day', () => {
    renderEdit();

    expect(within(editForm()).getByLabelText('Both')).toBeChecked();
    expect(within(editForm()).getByLabelText('Schedule')).toHaveValue('weekly');
    expect(within(editForm()).getByLabelText('Day')).toHaveValue('3');
  });

  it('patches the filters, columns, formats, schedule and day on Save', async () => {
    const bodies: unknown[] = [];
    const onDone = renderEdit(STORED, bodies);
    await screen.findByRole('button', { name: 'Columns' });

    await userEvent.selectOptions(screen.getByLabelText('Kind'), 'Members only');
    await userEvent.click(within(editForm()).getByLabelText('PDF'));
    await userEvent.selectOptions(within(editForm()).getByLabelText('Schedule'), 'Monthly');
    await userEvent.click(within(editForm()).getByRole('button', { name: 'Save changes' }));

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(bodies).toEqual([
      {
        filters: { kind: 'member', expiring_within: '30' },
        columns: ['name', 'county'],
        formats: 'pdf',
        cadence: 'monthly',
        weekday: 3,
      },
    ]);
  });

  it('sends a subscription on the default columns back with none chosen', async () => {
    const bodies: unknown[] = [];
    renderEdit(makeSubscription({ id: 6, columns: [] }), bodies);
    await screen.findByRole('button', { name: 'Columns' });

    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));

    await vi.waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toMatchObject({ columns: [] });
  });

  it('shows a refused filter by its label', async () => {
    renderEdit();
    server.use(
      http.patch(`${API}/reports/subscriptions/5`, () =>
        HttpResponse.json(
          { filters: { expiring_within: ['Enter a whole number.'] } },
          { status: 400 },
        ),
      ),
    );

    await userEvent.click(within(editForm()).getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Expiring within (days): Enter a whole number.',
    );
  });

  it('shows a refused column list under the chooser rather than above Save', async () => {
    renderEdit();
    await screen.findByRole('button', { name: 'Columns' });
    server.use(
      http.patch(`${API}/reports/subscriptions/5`, () =>
        HttpResponse.json({ columns: ['Unknown column: fax.'] }, { status: 400 }),
      ),
    );

    await userEvent.click(within(editForm()).getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Unknown column: fax.');
    expect(within(editForm()).queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows a refusal that names no field above Save', async () => {
    renderEdit();
    server.use(
      http.patch(`${API}/reports/subscriptions/5`, () =>
        HttpResponse.json({ detail: 'You may not change this subscription.' }, { status: 403 }),
      ),
    );

    await userEvent.click(within(editForm()).getByRole('button', { name: 'Save changes' }));

    expect(await within(editForm()).findByRole('alert')).toHaveTextContent(
      'You may not change this subscription.',
    );
  });

  it('saves the schedule of a subscription to a report the portal does not describe', async () => {
    const bodies: unknown[] = [];
    renderEdit(
      makeSubscription({ id: 7, report: 'retired', report_title: 'Retired report' }),
      bodies,
    );

    await userEvent.selectOptions(within(editForm()).getByLabelText('Schedule'), 'Yearly');
    await userEvent.click(within(editForm()).getByRole('button', { name: 'Save changes' }));

    await vi.waitFor(() => expect(bodies).toHaveLength(1));
    expect(bodies[0]).toMatchObject({ cadence: 'yearly' });
  });

  it('closes on Cancel without saving', async () => {
    const bodies: unknown[] = [];
    const onDone = renderEdit(STORED, bodies);

    await userEvent.click(within(editForm()).getByRole('button', { name: 'Cancel' }));

    expect(onDone).toHaveBeenCalled();
    expect(bodies).toEqual([]);
  });
});
