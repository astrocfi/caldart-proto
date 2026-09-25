import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { API, makeSubscription, subscriptionHandlers } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { ReportColumn, ReportSummary } from '@/portal/api/types';
import { SubscriptionForm } from './SubscriptionForm';

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
  return screen.getByRole('form', { name: 'New subscription' });
}

describe('SubscriptionForm', () => {
  it('offers only the reports the caller may read', async () => {
    renderForm();

    await screen.findByRole('option', { name: 'Members' });
    const offered = within(screen.getByLabelText('Report'))
      .getAllByRole('option')
      .map((option) => option.textContent);
    expect(offered).toEqual(['Choose a report…', 'Members', 'Payments', 'Contributions']);
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
          { slug: 'emails', title: 'Email log', choosable: true, periods: false },
        ],
      }),
    );
    const handleDone = vi.fn();
    renderWithProviders(<SubscriptionForm onDone={handleDone} />);

    await chooseReport('Email log');

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
    await userEvent.click(within(form()).getByRole('button', { name: 'Save' }));

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
    await userEvent.click(within(form()).getByRole('button', { name: 'Save' }));

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
    await userEvent.click(within(form()).getByRole('button', { name: 'Save' }));

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
    await userEvent.click(within(form()).getByRole('button', { name: 'Save' }));

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
          { confirmed: ['Tick the box to confirm this address may receive this report.'] },
          { status: 400 },
        );
      }),
    );
    await chooseReport('Members');

    const outside = 'This address is outside CalDART and may receive this report';
    expect(within(form()).queryByLabelText(outside)).not.toBeInTheDocument();
    await userEvent.type(within(form()).getByLabelText(/^Recipient email/), 'board@example.org');
    await userEvent.click(within(form()).getByRole('button', { name: 'Save' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Tick the box to confirm this address may receive this report.',
    );
    await userEvent.click(within(form()).getByLabelText(outside));
    await userEvent.click(within(form()).getByRole('button', { name: 'Save' }));

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
    await userEvent.click(within(form()).getByRole('button', { name: 'Save' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Period: Choose a valid period.');
  });

  it('asks for a report before it saves', async () => {
    const bodies: unknown[] = [];
    renderForm(bodies);
    await screen.findByRole('option', { name: 'Members' });

    expect(within(form()).getByRole('button', { name: 'Save' })).toBeDisabled();
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
