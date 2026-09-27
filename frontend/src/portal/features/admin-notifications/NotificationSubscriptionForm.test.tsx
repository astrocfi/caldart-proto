import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { NotificationSubscription } from '@/portal/api/types';
import { API, makeNotificationSubscription, notificationHandlers } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { NotificationSubscriptionForm } from './NotificationSubscriptionForm';

const SUBSCRIPTIONS_URL = `${API}/notifications/subscriptions`;

/** Render the form, new or editing `subscription`, and wait for the event boxes. */
async function renderForm(subscription?: NotificationSubscription, handleDone = vi.fn()) {
  renderWithProviders(
    <NotificationSubscriptionForm subscription={subscription} onDone={handleDone} />,
  );
  await screen.findByRole('checkbox', { name: 'Sign-up' });
  return handleDone;
}

/** Record every body sent to `method` at `url`, answering with `answer`. */
function recordBodies(
  method: 'post' | 'patch',
  url: string,
  answer: () => Response = () => HttpResponse.json(makeNotificationSubscription()),
): unknown[] {
  const bodies: unknown[] = [];
  server.use(
    http[method](url, async ({ request }) => {
      bodies.push(await request.json());
      return answer();
    }),
  );
  return bodies;
}

describe('NotificationSubscriptionForm', () => {
  beforeEach(() => {
    server.use(...notificationHandlers());
  });

  it('groups the events under their four categories', async () => {
    await renderForm();

    const legends = screen
      .getAllByRole('group')
      .map((group) => group.querySelector('legend')?.textContent);
    expect(legends).toEqual(['Membership', 'Money', 'Accounts', 'Aircraft']);
  });

  it("gives each event's box its description as a title", async () => {
    await renderForm();

    expect(
      screen.getByRole('checkbox', { name: 'Donation received' }).closest('label'),
    ).toHaveAttribute('title', 'A gift arrived.');
  });

  it('ticks every event of one category with Select all', async () => {
    await renderForm();
    const money = screen.getByRole('group', { name: 'Money' });

    await userEvent.click(within(money).getByRole('button', { name: 'Select all' }));

    expect(
      within(money)
        .getAllByRole('checkbox')
        .every((box) => (box as HTMLInputElement).checked),
    ).toBe(true);
  });

  it('leaves the other categories alone on Select all', async () => {
    await renderForm();

    await userEvent.click(
      within(screen.getByRole('group', { name: 'Money' })).getByRole('button', {
        name: 'Select all',
      }),
    );

    expect(screen.getByRole('checkbox', { name: 'Sign-up' })).not.toBeChecked();
  });

  it('unticks every event of one category with Clear', async () => {
    await renderForm(makeNotificationSubscription({ events: ['signed_up', 'donation_received'] }));

    await userEvent.click(
      within(screen.getByRole('group', { name: 'Membership' })).getByRole('button', {
        name: 'Clear',
      }),
    );

    expect(screen.getByRole('checkbox', { name: 'Sign-up' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Donation received' })).toBeChecked();
  });

  it('subscribes the address to the ticked events in catalog order', async () => {
    const bodies = recordBodies('post', SUBSCRIPTIONS_URL);
    const onDone = await renderForm();

    await userEvent.type(screen.getByLabelText(/Recipient email/), 'board@example.org');
    await userEvent.click(screen.getByRole('checkbox', { name: 'Aircraft added' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Sign-up' }));
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(bodies).toEqual([
      {
        recipient_email: 'board@example.org',
        events: ['signed_up', 'aircraft_added'],
        confirmed: false,
      },
    ]);
  });

  it('shows a refused address under the address', async () => {
    recordBodies('post', SUBSCRIPTIONS_URL, () =>
      HttpResponse.json(
        { recipient_email: ['This address already has a subscription.'] },
        { status: 400 },
      ),
    );
    await renderForm();

    await userEvent.type(screen.getByLabelText(/Recipient email/), 'ada@example.org');
    await userEvent.click(screen.getByRole('checkbox', { name: 'Sign-up' }));
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This address already has a subscription.',
    );
    expect(screen.getByLabelText(/Recipient email/)).toHaveAttribute('aria-invalid', 'true');
  });

  it('shows a refused event under the events', async () => {
    const message = 'Tessa Treasurer does not hold a role that may receive Sign-up.';
    recordBodies('post', SUBSCRIPTIONS_URL, () =>
      HttpResponse.json({ events: [message] }, { status: 400 }),
    );
    await renderForm();

    await userEvent.type(screen.getByLabelText(/Recipient email/), 'tessa@example.org');
    await userEvent.click(screen.getByRole('checkbox', { name: 'Sign-up' }));
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(message);
    expect(screen.getByLabelText(/Recipient email/)).not.toHaveAttribute('aria-invalid');
  });

  it('shows no confirmation box before the server asks for one', async () => {
    await renderForm();

    expect(screen.queryByRole('checkbox', { name: /outside CalDART/ })).not.toBeInTheDocument();
  });

  it('asks to confirm an address outside CalDART, and sends the tick', async () => {
    let calls = 0;
    const bodies = recordBodies('post', SUBSCRIPTIONS_URL, () => {
      calls += 1;
      return calls === 1
        ? HttpResponse.json(
            {
              confirmed: ['Tick the box to confirm this address may receive these notifications.'],
            },
            { status: 400 },
          )
        : HttpResponse.json(makeNotificationSubscription(), { status: 201 });
    });
    const onDone = await renderForm();

    await userEvent.type(screen.getByLabelText(/Recipient email/), 'board@example.org');
    await userEvent.click(screen.getByRole('checkbox', { name: 'Sign-up' }));
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    await userEvent.click(
      await screen.findByRole('checkbox', {
        name: 'This address is outside CalDART and may receive these notifications',
      }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(bodies[1]).toEqual({
      recipient_email: 'board@example.org',
      events: ['signed_up'],
      confirmed: true,
    });
  });

  it('shows the recipient of an edit as plain text', async () => {
    await renderForm(
      makeNotificationSubscription({ recipient_email: 'board@example.org', recipient_name: '' }),
    );

    expect(screen.getByRole('group', { name: 'Recipient' })).toHaveTextContent('board@example.org');
    expect(screen.queryByLabelText(/Recipient email/)).not.toBeInTheDocument();
  });

  it("starts an edit from the subscription's events", async () => {
    await renderForm(makeNotificationSubscription({ events: ['signed_up', 'payment_refunded'] }));

    const ticked = screen
      .getAllByRole('checkbox')
      .filter((box) => (box as HTMLInputElement).checked)
      .map((box) => box.getAttribute('name'));
    expect(ticked).toEqual(['signed_up', 'payment_refunded']);
  });

  it('saves an edit as a change of its events', async () => {
    const bodies = recordBodies('patch', `${SUBSCRIPTIONS_URL}/1`);
    const onDone = await renderForm(makeNotificationSubscription({ events: ['signed_up'] }));

    await userEvent.click(screen.getByRole('checkbox', { name: 'Sign-up' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Roles changed' }));
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));

    await vi.waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(bodies).toEqual([{ events: ['roles_changed'] }]);
  });

  it('closes on Cancel without saving', async () => {
    const bodies = recordBodies('post', SUBSCRIPTIONS_URL);
    const onDone = await renderForm();

    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onDone).toHaveBeenCalledTimes(1);
    expect(bodies).toEqual([]);
  });
});
