/**
 * `/donate` — the checkout's contribution form, with the recurring option, and
 * where a giver goes once the gift is made.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeContributionMandate, makePaymentsConfig } from '@test/fixtures/payments';
import type { MembershipStatus } from '@/portal/api/types';
import { API, makeUser, signedInAs } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import { DonatePage } from './DonatePage';

/** A friend of CalDART: no dues, no expiry. */
const FRIEND_MEMBERSHIP: MembershipStatus = {
  status: 'friend',
  expires_on: null,
  plan: null,
  is_lifetime: false,
};

/** Serve a friend's session and a mock-only checkout, and open `/donate`. */
function mount() {
  server.use(
    signedInAs(makeUser({ membership: FRIEND_MEMBERSHIP })),
    http.get(`${API}/payments/config`, () =>
      HttpResponse.json(makePaymentsConfig({ providers: ['mock'] })),
    ),
    http.post(`${API}/payments/checkout`, () =>
      HttpResponse.json({ payment_id: 91, provider: 'mock', client: {} }, { status: 201 }),
    ),
    http.post(`${API}/payments/mock/complete`, () =>
      HttpResponse.json({ status: 'succeeded', membership: FRIEND_MEMBERSHIP }),
    ),
  );
  return renderRoutes(
    [
      { path: '/donate', element: <DonatePage /> },
      { path: '/payments', element: <p>Payments screen</p> },
    ],
    { route: '/donate' },
  );
}

/** Serve a $25.00 monthly recurring donation in `status` as the signed-in person's. */
function holdDonation(status: 'active' | 'canceled'): void {
  server.use(
    http.get(`${API}/me/donation`, () =>
      HttpResponse.json({
        mandate: makeContributionMandate({ cadence: 'monthly', contribution_cents: 2500, status }),
      }),
    ),
  );
}

describe('DonatePage', () => {
  it('tells somebody who already gives on a schedule where to change it', async () => {
    holdDonation('active');
    mount();

    expect(
      await screen.findByText(
        'You already give $25.00 each month by recurring donation. To change it, press ' +
          'Change on Payments. A recurring donation set up here replaces it.',
      ),
    ).toBeInTheDocument();
  });

  it('links somebody who already gives on a schedule to Payments', async () => {
    holdDonation('active');
    mount();

    expect(await screen.findByRole('link', { name: 'Go to Payments' })).toHaveAttribute(
      'href',
      '/payments',
    );
  });

  it('says nothing of a recurring donation that is turned off', async () => {
    holdDonation('canceled');
    mount();

    await screen.findByRole('radio', { name: /Supporter/ });
    expect(screen.queryByRole('link', { name: 'Go to Payments' })).not.toBeInTheDocument();
  });

  it('is headed Donate', async () => {
    mount();

    expect(await screen.findByRole('heading', { name: 'Donate', level: 1 })).toBeInTheDocument();
  });

  it('offers a friend a gift with no plan to buy', async () => {
    mount();

    expect(await screen.findByRole('radio', { name: /Supporter/ })).toBeInTheDocument();
    expect(screen.queryByRole('radio', { name: /Annual/ })).not.toBeInTheDocument();
  });

  it('thanks the giver and goes to Payments once the gift is taken', async () => {
    const user = userEvent.setup();
    const { router } = mount();

    await user.click(await screen.findByRole('radio', { name: /Supporter/ }));
    await user.click(screen.getByRole('button', { name: 'Succeed' }));

    await waitFor(() => expect(router.state.location.pathname).toBe('/payments'));
    expect(await screen.findByText('Thank you for your donation.')).toBeInTheDocument();
  });
});
