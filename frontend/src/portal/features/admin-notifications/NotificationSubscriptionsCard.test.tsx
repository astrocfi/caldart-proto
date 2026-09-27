import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { API, makeNotificationSubscription, notificationHandlers } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { NotificationSubscriptionsCard } from './NotificationSubscriptionsCard';
import type { NotificationSubscription } from './types';

const ADA = makeNotificationSubscription({ id: 1, events: ['signed_up', 'became_member'] });

const BOARD = makeNotificationSubscription({
  id: 2,
  recipient_user: null,
  recipient_name: '',
  recipient_email: 'board@example.org',
  events: ['donation_received'],
  is_active: false,
});

/** Render the card over `subscriptions`, and wait for the table to fill. */
async function renderCard(subscriptions: NotificationSubscription[] = [ADA, BOARD]) {
  server.use(...notificationHandlers({ subscriptions }));
  renderWithProviders(<NotificationSubscriptionsCard />);
  return screen.findByRole('table', { name: /^[1-9]\d* subscriptions?$/ });
}

/** The table row naming `name`. */
function row(table: HTMLElement, name: RegExp): HTMLElement {
  return within(table).getByRole('row', { name });
}

describe('NotificationSubscriptionsCard', () => {
  it('is headed Who hears about what', async () => {
    await renderCard();

    expect(screen.getByRole('heading', { name: 'Who hears about what' })).toBeInTheDocument();
  });

  it('names the account a subscription is bound to', async () => {
    const table = await renderCard();

    expect(row(table, /Ada Admin/)).toBeInTheDocument();
  });

  it('gives the bare address of a recipient outside CalDART', async () => {
    const table = await renderCard();

    expect(row(table, /board@example.org/)).toBeInTheDocument();
  });

  it('lists the labels of the events, joined with commas', async () => {
    const table = await renderCard();

    expect(
      within(row(table, /Ada Admin/)).getByRole('cell', {
        name: 'Sign-up, Friend became a member',
      }),
    ).toBeInTheDocument();
  });

  it('keeps the full list of events in the cell title', async () => {
    const table = await renderCard();

    expect(
      within(row(table, /Ada Admin/)).getByTitle('Sign-up, Friend became a member'),
    ).toBeInTheDocument();
  });

  it('marks a paused subscription with a dot', async () => {
    const table = await renderCard();

    expect(within(row(table, /board@example.org/)).getByTitle('Paused')).toBeInTheDocument();
  });

  it('marks an active subscription with a dot', async () => {
    const table = await renderCard();

    expect(within(row(table, /Ada Admin/)).getByTitle('Active')).toBeInTheDocument();
  });

  it('gives each row Edit, Pause or Resume, and the trashcan, in that order', async () => {
    const table = await renderCard();

    const controls = within(row(table, /Ada Admin/))
      .getAllByRole('button')
      .map((button) => button.getAttribute('aria-label') ?? button.textContent);
    expect(controls).toEqual(['Edit', 'Pause', 'Delete subscription']);
  });

  it('pauses an active subscription', async () => {
    const bodies: unknown[] = [];
    const table = await renderCard();
    server.use(
      http.patch(`${API}/notifications/subscriptions/1`, async ({ request }) => {
        bodies.push(await request.json());
        return HttpResponse.json({ ...ADA, is_active: false });
      }),
    );

    await userEvent.click(within(row(table, /Ada Admin/)).getByRole('button', { name: 'Pause' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Paused.');
    expect(bodies).toEqual([{ is_active: false }]);
  });

  it('resumes a paused subscription', async () => {
    const table = await renderCard();

    await userEvent.click(
      within(row(table, /board@example.org/)).getByRole('button', { name: 'Resume' }),
    );

    expect(await screen.findByRole('status')).toHaveTextContent('Resumed.');
    await vi.waitFor(() =>
      expect(within(row(table, /board@example.org/)).getByTitle('Active')).toBeInTheDocument(),
    );
  });

  it('shows why a subscription could not be resumed', async () => {
    const message = 'Tessa Treasurer does not hold a role that may receive Donation received.';
    const table = await renderCard();
    server.use(
      http.patch(`${API}/notifications/subscriptions/2`, () =>
        HttpResponse.json({ events: [message] }, { status: 400 }),
      ),
    );

    await userEvent.click(
      within(row(table, /board@example.org/)).getByRole('button', { name: 'Resume' }),
    );

    expect(await screen.findByRole('status')).toHaveTextContent(message);
  });

  it('deletes a subscription with the trashcan', async () => {
    const table = await renderCard();

    await userEvent.click(
      within(row(table, /Ada Admin/)).getByRole('button', { name: 'Delete subscription' }),
    );

    expect(await screen.findByRole('status')).toHaveTextContent('Deleted.');
    await vi.waitFor(() =>
      expect(within(table).queryByRole('row', { name: /Ada Admin/ })).not.toBeInTheDocument(),
    );
  });

  it('says so when nobody is subscribed', async () => {
    server.use(...notificationHandlers());
    renderWithProviders(<NotificationSubscriptionsCard />);

    expect(
      await screen.findByText('Nobody is subscribed to a notification yet'),
    ).toBeInTheDocument();
  });

  it('opens the form under the table from New subscription', async () => {
    const table = await renderCard();

    await userEvent.click(screen.getByRole('button', { name: 'New subscription' }));

    const form = screen.getByRole('form', { name: 'New subscription' });
    expect(table.compareDocumentPosition(form) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('opens the edit form for the row whose Edit was pressed', async () => {
    const table = await renderCard();

    await userEvent.click(
      within(row(table, /board@example.org/)).getByRole('button', { name: 'Edit' }),
    );

    expect(screen.getByRole('group', { name: 'Recipient' })).toHaveTextContent('board@example.org');
  });

  it("closes the edit form when the same row's Edit is pressed again", async () => {
    const table = await renderCard();
    const edit = within(row(table, /Ada Admin/)).getByRole('button', { name: 'Edit' });

    await userEvent.click(edit);
    await userEvent.click(edit);

    expect(screen.queryByRole('form', { name: 'Edit subscription' })).not.toBeInTheDocument();
  });

  it('closes an open edit when New subscription is pressed', async () => {
    const table = await renderCard();

    await userEvent.click(within(row(table, /Ada Admin/)).getByRole('button', { name: 'Edit' }));
    await userEvent.click(screen.getByRole('button', { name: 'New subscription' }));

    expect(screen.queryByRole('form', { name: 'Edit subscription' })).not.toBeInTheDocument();
  });

  it('shows a new subscription in the table and closes the form', async () => {
    const table = await renderCard();

    await userEvent.click(screen.getByRole('button', { name: 'New subscription' }));
    const form = await screen.findByRole('form', { name: 'New subscription' });
    await userEvent.type(within(form).getByLabelText(/Recipient email/), 'dart@example.org');
    await userEvent.click(await within(form).findByRole('checkbox', { name: 'Aircraft added' }));
    await userEvent.click(within(form).getByRole('button', { name: 'Save' }));

    await vi.waitFor(() =>
      expect(row(table, /dart@example.org/)).toHaveTextContent('Aircraft added'),
    );
    expect(screen.queryByRole('form', { name: 'New subscription' })).not.toBeInTheDocument();
  });

  it('shows the saved events in the row and closes the edit form', async () => {
    const table = await renderCard();

    await userEvent.click(within(row(table, /Ada Admin/)).getByRole('button', { name: 'Edit' }));
    const form = screen.getByRole('form', { name: 'Edit subscription' });
    await userEvent.click(await within(form).findByRole('checkbox', { name: 'Sign-up' }));
    await userEvent.click(within(form).getByRole('button', { name: 'Save' }));

    await vi.waitFor(() =>
      expect(
        within(row(table, /Ada Admin/)).getByRole('cell', { name: 'Friend became a member' }),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByRole('form', { name: 'Edit subscription' })).not.toBeInTheDocument();
  });
});
