import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API, makeSubscription, subscriptionHandlers } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { ReportRunResult, ReportSubscription } from '@/portal/api/types';
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

/** Render the card over `subscriptions`, and wait for the table to fill. */
async function renderCard(subscriptions: ReportSubscription[] = [MEMBERS, PAYMENTS]) {
  server.use(...subscriptionHandlers({ subscriptions }));
  renderWithProviders(<SubscriptionsCard />);
  return screen.findByRole('table', { name: /^[1-9]\d* subscriptions?$/ });
}

/** The table row naming `name`. */
function row(table: HTMLElement, name: RegExp): HTMLElement {
  return within(table).getByRole('row', { name });
}

describe('SubscriptionsCard', () => {
  it('names the report, the recipient, the schedule and the formats of each', async () => {
    const table = await renderCard();

    expect(row(table, /Ada Admin/)).toHaveTextContent('MembersAda AdminMonthlyPDF');
    expect(row(table, /board@example.org/)).toHaveTextContent(
      'Paymentsboard@example.orgWeekly on FridayBoth',
    );
  });

  it('dates the last send and the next one', async () => {
    const table = await renderCard();

    expect(row(table, /Ada Admin/)).toHaveTextContent('2026/09/15');
    expect(row(table, /Ada Admin/)).toHaveTextContent('2026/10/01');
  });

  it('marks a paused subscription as paused', async () => {
    const table = await renderCard();

    expect(within(row(table, /board@example.org/)).getByTitle('Paused')).toBeInTheDocument();
  });

  it('says who a sent report reached', async () => {
    const table = await renderCard();
    server.use(http.post(`${API}/reports/subscriptions/1/send`, () => HttpResponse.json(sent())));

    await userEvent.click(
      within(row(table, /Ada Admin/)).getByRole('button', { name: 'Send now' }),
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
      within(row(table, /Ada Admin/)).getByRole('button', { name: 'Send now' }),
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
      within(row(table, /Ada Admin/)).getByRole('button', { name: 'Send now' }),
    );

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Not sent: Ada Admin no longer holds a role that may read this report, so the ' +
        'subscription is paused.',
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

    await userEvent.click(within(row(table, /Ada Admin/)).getByRole('button', { name: 'Pause' }));

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
      within(row(table, /board@example.org/)).getByRole('button', { name: 'Resume' }),
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
      within(row(table, /board@example.org/)).getByRole('button', { name: 'Resume' }),
    );

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Tessa Treasurer does not hold a role that may read this report.',
    );
  });

  it('deletes a subscription with the trashcan', async () => {
    const deleted: string[] = [];
    const table = await renderCard();
    server.use(
      http.delete(`${API}/reports/subscriptions/:id`, ({ params }) => {
        deleted.push(String(params.id));
        return new HttpResponse(null, { status: 204 });
      }),
    );

    await userEvent.click(
      within(row(table, /Ada Admin/)).getByRole('button', { name: 'Delete subscription' }),
    );

    expect(await screen.findByRole('status')).toHaveTextContent('Deleted.');
    expect(deleted).toEqual(['1']);
  });

  it('says so when there are no subscriptions', async () => {
    server.use(...subscriptionHandlers({ subscriptions: [] }));
    renderWithProviders(<SubscriptionsCard />);

    expect(await screen.findByText('No reports are sent by email yet')).toBeInTheDocument();
  });

  it('opens the form from New subscription', async () => {
    await renderCard();

    await userEvent.click(screen.getByRole('button', { name: 'New subscription' }));

    expect(screen.getByRole('form', { name: 'New subscription' })).toBeInTheDocument();
  });
});
