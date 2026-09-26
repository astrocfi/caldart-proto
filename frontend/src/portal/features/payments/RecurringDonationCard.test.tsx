/**
 * The Recurring donation card, one test per state the donation can be in.
 *
 * It is the renewal's card over the other authority, so these tests check what
 * differs: it is headed Recurring donation, says how often it charges, links to
 * the Donate screen to set one up, and talks to `/me/donation`.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { RenewalEnvelope, RenewalMandate } from '@/portal/api/types';
import { makeContributionMandate, makeMandate, makePaymentsConfig } from '@test/fixtures/payments';
import { API, LIFETIME_MEMBERSHIP, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { RecurringDonationCard } from './RecurringDonationCard';

/** Serve `GET /me/donation` with `mandate` and render the card at `route`. */
function mount(mandate: RenewalMandate | null, { route = '/payments' }: { route?: string } = {}) {
  server.use(
    signedInAs(makeUser({ membership: LIFETIME_MEMBERSHIP })),
    http.get(`${API}/me/membership`, () =>
      HttpResponse.json({ ...LIFETIME_MEMBERSHIP, history: [] }),
    ),
    http.get(`${API}/me/donation`, () => HttpResponse.json({ mandate } satisfies RenewalEnvelope)),
    http.get(`${API}/payments/config`, () => HttpResponse.json(makePaymentsConfig())),
  );
  return renderWithProviders(<RecurringDonationCard />, { route });
}

/** A monthly donation of $25.00, next charged on 2026/11/05. */
function monthly(overrides: Partial<RenewalMandate> = {}): RenewalMandate {
  return makeContributionMandate({
    cadence: 'monthly',
    contribution_cents: 2500,
    amount_cents: 2500,
    next_charge_on: '2026-11-05',
    ...overrides,
  });
}

/** Record every `PATCH /me/donation` body, answering with `mandate` each time. */
function recordPatches(mandate: RenewalMandate): unknown[] {
  const bodies: unknown[] = [];
  server.use(
    http.patch(`${API}/me/donation`, async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json({ mandate } satisfies RenewalEnvelope);
    }),
  );
  return bodies;
}

describe('RecurringDonationCard', () => {
  it('is headed Recurring donation', async () => {
    mount(null);

    expect(await screen.findByRole('heading', { name: 'Recurring donation' })).toBeInTheDocument();
  });

  it('sends somebody with no donation to the Donate screen to set one up', async () => {
    mount(null);

    expect(await screen.findByRole('link', { name: 'Set up' })).toHaveAttribute('href', '/donate');
  });

  it('says what a donation would do when there is none', async () => {
    mount(null);

    expect(
      await screen.findByText(
        'Set one up on the Donate screen and CalDART will charge a saved card or PayPal account ' +
          'monthly, quarterly, or yearly, for the amount you choose.',
      ),
    ).toBeInTheDocument();
  });

  it('names how often an active donation charges', async () => {
    mount(monthly());

    expect(await screen.findByText('How often')).toBeInTheDocument();
    expect(screen.getByText('How often').nextElementSibling).toHaveTextContent('Monthly');
  });

  it('names the day and the amount of the next charge', async () => {
    mount(monthly());

    expect(await screen.findByText('Next charge')).toBeInTheDocument();
    expect(screen.getByText('Next charge').nextElementSibling).toHaveTextContent(
      '2026/11/05 · $25.00',
    );
  });

  it('promises a receipt rather than a notice for a monthly donation', async () => {
    mount(monthly());

    expect(await screen.findByText('We email you a receipt after every charge.')).toBeVisible();
  });

  it('promises the fortnight notice for a yearly donation', async () => {
    mount(monthly({ cadence: 'yearly' }));

    expect(
      await screen.findByText('We will email you fourteen days before every charge.'),
    ).toBeVisible();
  });

  it('names no plan, because a donation renews nothing', async () => {
    mount(monthly());

    expect(await screen.findByText('Amount')).toBeInTheDocument();
    expect(screen.queryByText('Plan')).not.toBeInTheDocument();
  });

  it('says the donation stopped, and why, when the charge was refused', async () => {
    mount(monthly({ status: 'paused', last_error: 'Your card was declined' }));

    expect(
      await screen.findByText(/Your recurring donation stopped because CalDART could not charge/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Your card was declined/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Set up' })).toBeInTheDocument();
  });

  it('opens the change form with the cadence the donation already carries', async () => {
    const user = userEvent.setup();
    mount(monthly());

    await user.click(await screen.findByRole('button', { name: 'Change' }));

    expect(
      screen.getByRole('heading', { name: 'Change your recurring donation' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Monthly' })).toBeChecked();
  });

  it('changes the amount and the cadence without naming a plan', async () => {
    const user = userEvent.setup();
    mount(monthly());
    const bodies = recordPatches(monthly({ cadence: 'quarterly' }));

    await user.click(await screen.findByRole('button', { name: 'Change' }));
    expect(screen.queryByRole('radio', { name: /Annual/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole('radio', { name: 'Quarterly' }));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() =>
      expect(bodies).toEqual([
        { contribution_cents: 2500, next_charge_on: '2026-11-05', cadence: 'quarterly' },
      ]),
    );
  });

  it('will not save a donation of nothing', async () => {
    const user = userEvent.setup();
    mount(monthly());

    await user.click(await screen.findByRole('button', { name: 'Change' }));
    await user.click(screen.getByRole('radio', { name: /No thank you/ }));

    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();
    expect(screen.getByText('Choose an amount to give.')).toBeVisible();
  });

  it('turns the donation off through its own endpoint and says so', async () => {
    const user = userEvent.setup();
    mount(monthly());
    server.use(http.delete(`${API}/me/donation`, () => new HttpResponse(null, { status: 204 })));

    await user.click(await screen.findByRole('button', { name: 'Turn off' }));
    expect(screen.getByText(/Turn your recurring donation off\?/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Yes, turn it off' }));

    expect(await screen.findByText('Recurring donation is off.')).toBeInTheDocument();
  });

  it('confirms a returning SetupIntent only when the return names the donation', async () => {
    const confirms: unknown[] = [];
    server.use(
      http.post(`${API}/me/donation/confirm`, async ({ request }) => {
        confirms.push(await request.json());
        return HttpResponse.json({ mandate: monthly() } satisfies RenewalEnvelope);
      }),
    );
    mount(monthly({ status: 'pending' }), {
      route: '/payments?setup_intent=seti_donation&mandate=donation',
    });

    await waitFor(() =>
      expect(confirms).toEqual([{ setup_intent_id: 'seti_donation', setup_token: '' }]),
    );
  });

  it('leaves a returning SetupIntent for the renewal to the renewal card', async () => {
    const confirms: unknown[] = [];
    server.use(
      http.post(`${API}/me/donation/confirm`, async ({ request }) => {
        confirms.push(await request.json());
        return HttpResponse.json({ mandate: makeMandate() } satisfies RenewalEnvelope);
      }),
    );
    mount(null, { route: '/payments?setup_intent=seti_renewal' });

    expect(await screen.findByText('Off')).toBeInTheDocument();
    expect(confirms).toEqual([]);
  });
});
