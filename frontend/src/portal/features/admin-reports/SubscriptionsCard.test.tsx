import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { API, makeSubscription, subscriptionHandlers } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { ReportColumn, ReportRunResult, ReportSubscription } from '@/portal/api/types';
import { SubscriptionsCard } from './SubscriptionsCard';

const MEMBERS = makeSubscription({
  id: 1,
  last_sent_at: '2026-09-15T18:00:04Z',
  next_due_on: '2026-10-01',
});

const PAYMENTS = makeSubscription({
  id: 2,
  report: 'payments',
  report_title: 'Payments',
  recipient_user: null,
  recipient_name: '',
  recipient_email: 'board@example.org',
  formats: 'both',
  cadence: 'weekly',
  weekday: 4,
  is_active: false,
  next_due_on: '2026-10-02',
});

function sent(overrides: Partial<ReportRunResult> = {}): ReportRunResult {
  return { sent: 1, skipped: 0, failed: 0, skipped_by_reason: {}, actions: [], ...overrides };
}

const COLUMNS: ReportColumn[] = [
  { key: 'name', label: 'Name', default: true },
  { key: 'email', label: 'Email', default: true },
];

/** Render the card over `subscriptions`, and wait for the table to fill. */
async function renderCard(subscriptions: ReportSubscription[] = [MEMBERS, PAYMENTS]) {
  server.use(
    ...subscriptionHandlers({ subscriptions }),
    http.get(`${API}/reports/:slug/columns`, () => HttpResponse.json(COLUMNS)),
  );
  renderWithProviders(<SubscriptionsCard />);
  return screen.findByRole('table', { name: /^[1-9]\d* emailed reports?$/ });
}

/** The table row naming `name`. */
function row(table: HTMLElement, name: RegExp): HTMLElement {
  return within(table).getByRole('row', { name });
}

describe('SubscriptionsCard', () => {
  it('heads the actions column for a screen reader, and draws it last', async () => {
    const table = await renderCard();
    expect(within(table).getAllByRole('columnheader').at(-1)).toHaveTextContent('Actions');
  });

  it('names the report, the recipient, the schedule and the formats of each', async () => {
    const table = await renderCard();

    expect(row(table, /Ada Admin/)).toHaveTextContent('MembersAda AdminMonthlyPDF');
    expect(row(table, /board@example.org/)).toHaveTextContent(
      'Paymentsboard@example.orgWeekly on FridayBoth',
    );
  });

  it('names a report as its tab does, not by the title its PDF carries', async () => {
    const table = await renderCard([
      { ...PAYMENTS, report: 'reconciliation', report_title: 'CalDART reconciliation' },
    ]);

    expect(within(table).getByRole('rowheader', { name: 'Reconciliation' })).toBeInTheDocument();
  });

  it('dates the last send and the next one', async () => {
    const table = await renderCard();

    expect(row(table, /Ada Admin/)).toHaveTextContent('09/15/2026');
    expect(row(table, /Ada Admin/)).toHaveTextContent('10/01/2026');
  });

  it('marks a paused subscription as paused', async () => {
    const table = await renderCard();

    expect(within(row(table, /board@example.org/)).getByText('Paused')).toHaveAttribute(
      'data-tone',
      'none',
    );
  });

  it('opens Edit above the table, where Add a scheduled report opens', async () => {
    const user = userEvent.setup();
    const table = await renderCard();

    await user.click(within(row(table, /Ada Admin/)).getByRole('button', { name: /^Edit / }));

    const form = screen.getByRole('form', { name: 'Edit emailed report' });
    expect(form.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('moves the focus into the form it opens and back to Edit on Escape', async () => {
    const user = userEvent.setup();
    const table = await renderCard();
    const edit = within(row(table, /Ada Admin/)).getByRole('button', { name: /^Edit / });

    await user.click(edit);
    await user.keyboard('{Escape}');

    expect(edit).toHaveFocus();
  });

  it('says who a sent report reached', async () => {
    const table = await renderCard();
    server.use(http.post(`${API}/reports/subscriptions/1/send`, () => HttpResponse.json(sent())));

    await userEvent.click(
      within(row(table, /Ada Admin/)).getByRole('button', { name: /^Send now: / }),
    );

    expect(await screen.findByRole('status')).toHaveTextContent('Sent to Ada Admin.');
  });

  it('says when the mail server refused the send', async () => {
    const table = await renderCard();
    server.use(
      http.post(`${API}/reports/subscriptions/1/send`, () =>
        HttpResponse.json(sent({ sent: 0, failed: 1 })),
      ),
    );

    await userEvent.click(
      within(row(table, /Ada Admin/)).getByRole('button', { name: /^Send now: / }),
    );

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Not sent to Ada Admin: the report could not be built or the mail server refused it.',
    );
  });

  it('says when the recipient may no longer read the report', async () => {
    const table = await renderCard();
    server.use(
      http.post(`${API}/reports/subscriptions/1/send`, () =>
        HttpResponse.json(sent({ sent: 0, skipped: 1, skipped_by_reason: { not_permitted: 1 } })),
      ),
    );

    await userEvent.click(
      within(row(table, /Ada Admin/)).getByRole('button', { name: /^Send now: / }),
    );

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Not sent: Ada Admin no longer holds a role that may read this report, so its emails ' +
        'are paused.',
    );
  });

  it('pauses an active subscription', async () => {
    const bodies: unknown[] = [];
    const table = await renderCard();
    server.use(
      http.patch(`${API}/reports/subscriptions/1`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ ...MEMBERS, is_active: false });
      }),
    );

    await userEvent.click(within(row(table, /Ada Admin/)).getByRole('button', { name: /^Pause / }));

    expect(await screen.findByRole('status')).toHaveTextContent('Paused.');
    expect(bodies).toEqual([{ is_active: false }]);
  });

  it('resumes a paused subscription', async () => {
    const bodies: unknown[] = [];
    const table = await renderCard();
    server.use(
      http.patch(`${API}/reports/subscriptions/2`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ ...PAYMENTS, is_active: true });
      }),
    );

    await userEvent.click(
      within(row(table, /board@example.org/)).getByRole('button', { name: /^Resume / }),
    );

    expect(await screen.findByRole('status')).toHaveTextContent('Resumed.');
    expect(bodies).toEqual([{ is_active: true }]);
  });

  it('shows why a subscription could not be resumed', async () => {
    const table = await renderCard();
    server.use(
      http.patch(`${API}/reports/subscriptions/2`, () =>
        HttpResponse.json(
          { is_active: ['Tessa Treasurer does not hold a role that may read this report.'] },
          { status: 400 },
        ),
      ),
    );

    await userEvent.click(
      within(row(table, /board@example.org/)).getByRole('button', { name: /^Resume / }),
    );

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Tessa Treasurer does not hold a role that may read this report.',
    );
  });

  it('does nothing to a subscription on the first press of its trashcan', async () => {
    const deleted: string[] = [];
    const table = await renderCard();
    server.use(
      http.delete(`${API}/reports/subscriptions/:id`, ({ params }) => {
        deleted.push(String(params.id));
        return new HttpResponse(null, { status: 204 });
      }),
    );

    await userEvent.click(
      within(row(table, /Ada Admin/)).getByRole('button', { name: /^Delete / }),
    );

    expect(deleted).toEqual([]);
  });

  it('deletes a subscription once its trashcan is confirmed', async () => {
    const deleted: string[] = [];
    const table = await renderCard();
    server.use(
      http.delete(`${API}/reports/subscriptions/:id`, ({ params }) => {
        deleted.push(String(params.id));
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const target = row(table, /Ada Admin/);

    await userEvent.click(within(target).getByRole('button', { name: /^Delete / }));
    await userEvent.click(within(target).getByRole('button', { name: 'Delete' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Deleted.');
    expect(deleted).toEqual(['1']);
  });

  it('says so when there are no subscriptions', async () => {
    server.use(...subscriptionHandlers({ subscriptions: [] }));
    renderWithProviders(<SubscriptionsCard />);

    expect(await screen.findByText('No reports are sent by email yet')).toBeInTheDocument();
  });

  it('opens the form from Add a scheduled report', async () => {
    await renderCard();

    await userEvent.click(screen.getByRole('button', { name: 'Add a scheduled report' }));

    expect(screen.getByRole('form', { name: 'Add a scheduled report' })).toBeInTheDocument();
  });

  it('opens the edit form for the row whose Edit was pressed', async () => {
    const table = await renderCard();

    await userEvent.click(
      within(row(table, /board@example.org/)).getByRole('button', { name: /^Edit / }),
    );

    const edit = screen.getByRole('form', { name: 'Edit emailed report' });
    expect(within(edit).getByRole('group', { name: 'Recipient' })).toHaveTextContent(
      'board@example.org',
    );
  });

  it("names a paused row's Resume for its report and recipient", async () => {
    const table = await renderCard();

    expect(
      within(row(table, /board@example.org/)).getByRole('button', {
        name: 'Resume Payments for board@example.org',
      }),
    ).toBeInTheDocument();
  });

  it('puts Edit first among the row controls', async () => {
    const table = await renderCard();

    const controls = within(row(table, /Ada Admin/))
      .getAllByRole('button')
      .map((button) => button.getAttribute('aria-label') ?? button.textContent);
    expect(controls).toEqual([
      'Edit Members for Ada Admin',
      'Send now: Members for Ada Admin',
      'Pause Members for Ada Admin',
      'Delete Members for Ada Admin',
    ]);
  });

  it('swaps the edit form to the row whose Edit was pressed next', async () => {
    const table = await renderCard();

    await userEvent.click(within(row(table, /Ada Admin/)).getByRole('button', { name: /^Edit / }));
    await userEvent.click(
      within(row(table, /board@example.org/)).getByRole('button', { name: /^Edit / }),
    );

    expect(screen.getAllByRole('form', { name: 'Edit emailed report' })).toHaveLength(1);
    expect(screen.getByRole('group', { name: 'Recipient' })).toHaveTextContent('board@example.org');
  });

  it("closes the edit form when the same row's Edit is pressed again", async () => {
    const table = await renderCard();
    const edit = within(row(table, /Ada Admin/)).getByRole('button', { name: /^Edit / });

    await userEvent.click(edit);
    await userEvent.click(edit);

    expect(screen.queryByRole('form', { name: 'Edit emailed report' })).not.toBeInTheDocument();
  });

  it('closes an open edit when Add a scheduled report is pressed', async () => {
    const table = await renderCard();

    await userEvent.click(within(row(table, /Ada Admin/)).getByRole('button', { name: /^Edit / }));
    await userEvent.click(screen.getByRole('button', { name: 'Add a scheduled report' }));

    expect(screen.queryByRole('form', { name: 'Edit emailed report' })).not.toBeInTheDocument();
    expect(screen.getByRole('form', { name: 'Add a scheduled report' })).toBeInTheDocument();
  });

  it('closes the Add a scheduled report form when Edit is pressed', async () => {
    const table = await renderCard();

    await userEvent.click(screen.getByRole('button', { name: 'Add a scheduled report' }));
    await userEvent.click(within(row(table, /Ada Admin/)).getByRole('button', { name: /^Edit / }));

    expect(screen.queryByRole('form', { name: 'Add a scheduled report' })).not.toBeInTheDocument();
    expect(screen.getByRole('form', { name: 'Edit emailed report' })).toBeInTheDocument();
  });

  it('shows the saved change in the row and closes the form', async () => {
    const table = await renderCard();

    await userEvent.click(within(row(table, /Ada Admin/)).getByRole('button', { name: /^Edit / }));
    const edit = screen.getByRole('form', { name: 'Edit emailed report' });
    await userEvent.selectOptions(within(edit).getByLabelText('Schedule'), 'Weekly');
    await userEvent.selectOptions(within(edit).getByLabelText('Day'), 'Thursday');
    await userEvent.click(within(edit).getByRole('button', { name: 'Save changes' }));

    await vi.waitFor(() => expect(row(table, /Ada Admin/)).toHaveTextContent('Weekly on Thursday'));
    expect(screen.queryByRole('form', { name: 'Edit emailed report' })).not.toBeInTheDocument();
  });

  it('closes the edit form on Cancel', async () => {
    const table = await renderCard();

    await userEvent.click(within(row(table, /Ada Admin/)).getByRole('button', { name: /^Edit / }));
    await userEvent.click(
      within(screen.getByRole('form', { name: 'Edit emailed report' })).getByRole('button', {
        name: 'Cancel',
      }),
    );

    expect(screen.queryByRole('form', { name: 'Edit emailed report' })).not.toBeInTheDocument();
  });
});
