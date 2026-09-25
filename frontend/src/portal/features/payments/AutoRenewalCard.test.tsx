/**
 * The Automatic renewal card, one test per state the mandate can be in.
 *
 * The card is the only thing on the screen that says whether CalDART is going
 * to take money, so each state is checked for the sentence that answers that
 * and for the control that changes it.  A life member's card is about their
 * contribution: their membership never runs out, so nothing of theirs renews.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { MembershipStatus, RenewalEnvelope, RenewalMandate } from '@/portal/api/types';
import { makeContributionMandate, makeMandate, makePaymentsConfig } from '@test/fixtures/payments';
import { API, CURRENT_MEMBERSHIP, LIFETIME_MEMBERSHIP, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { AutoRenewalCard } from './AutoRenewalCard';

/** Serve `GET /me/renewal` with `mandate` and render the card at `route`. */
function mount(
  mandate: RenewalMandate | null,
  {
    route = '/payments',
    membership = CURRENT_MEMBERSHIP,
    hasMembership = true,
  }: { route?: string; membership?: MembershipStatus; hasMembership?: boolean } = {},
) {
  server.use(
    signedInAs(makeUser({ membership })),
    http.get(`${API}/me/membership`, () =>
      hasMembership
        ? HttpResponse.json({ ...membership, history: [] })
        : HttpResponse.json({ detail: 'Server error.' }, { status: 500 }),
    ),
    http.get(`${API}/me/renewal`, () => HttpResponse.json({ mandate } satisfies RenewalEnvelope)),
    http.get(`${API}/payments/config`, () => HttpResponse.json(makePaymentsConfig())),
  );
  return renderWithProviders(<AutoRenewalCard />, { route });
}

/** Render the card with `GET /me/renewal` failing outright. */
function mountUnreadable() {
  server.use(
    signedInAs(makeUser()),
    http.get(`${API}/me/membership`, () =>
      HttpResponse.json({ ...CURRENT_MEMBERSHIP, history: [] }),
    ),
    http.get(`${API}/me/renewal`, () =>
      HttpResponse.json({ detail: 'Server error.' }, { status: 500 }),
    ),
  );
  return renderWithProviders(<AutoRenewalCard />, { route: '/payments' });
}

/** Record every `PATCH /me/renewal` body, answering with `mandate` each time. */
function recordPatches(mandate: RenewalMandate): unknown[] {
  const bodies: unknown[] = [];
  server.use(
    http.patch(`${API}/me/renewal`, async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json({ mandate } satisfies RenewalEnvelope);
    }),
  );
  return bodies;
}

describe('AutoRenewalCard', () => {
  it('offers to turn renewal on when the member has never had a mandate', async () => {
    mount(null);

    expect(await screen.findByText('Off')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Turn on' })).toBeInTheDocument();
  });

  it('treats an unfinished setup as off, so the only way forward is to start again', async () => {
    mount(makeMandate({ status: 'pending' }));

    expect(await screen.findByText('Off')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Turn on' })).toBeInTheDocument();
  });

  it('names the method, the next charge date and the amount when renewal is on', async () => {
    mount(makeMandate({ next_charge_on: '2027-03-12', amount_cents: 7000 }));

    expect(await screen.findByText('On')).toBeInTheDocument();
    expect(screen.getByText('Visa ending 4242, expires 03/2028')).toBeInTheDocument();
    expect(screen.getByText('2027/03/12')).toBeInTheDocument();
    expect(screen.getByText('$70.00')).toBeInTheDocument();
  });

  it('promises the warning email in the words the setup flow uses', async () => {
    mount(makeMandate());

    expect(
      await screen.findByText(/We will email you fourteen days before every charge\./),
    ).toBeInTheDocument();
  });

  it('gives the reason the last charge was refused when the mandate is paused', async () => {
    mount(
      makeMandate({
        status: 'paused',
        failure_count: 3,
        last_error: 'Your card was declined',
      }),
    );

    expect(await screen.findByText('Stopped')).toBeInTheDocument();
    expect(screen.getByText(/Your card was declined/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Turn on again' })).toBeInTheDocument();
  });

  it('says when a canceled mandate was turned off', async () => {
    mount(makeMandate({ status: 'canceled', canceled_at: '2026-05-04T10:00:00Z' }));

    expect(await screen.findByText('Off')).toBeInTheDocument();
    expect(screen.getByText('2026/05/04')).toBeInTheDocument();
  });

  it('asks before turning renewal off, and reports it once the server agrees', async () => {
    const user = userEvent.setup();
    mount(makeMandate());
    server.use(http.delete(`${API}/me/renewal`, () => new HttpResponse(null, { status: 204 })));

    await user.click(await screen.findByRole('button', { name: 'Turn off' }));
    expect(screen.getByText(/Turn automatic renewal off\?/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Yes, turn it off' }));

    expect(await screen.findByText('Automatic renewal is off.')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('Off')).toBeInTheDocument());
  });

  it('keeps the mandate when the confirmation is declined', async () => {
    const user = userEvent.setup();
    mount(makeMandate());

    await user.click(await screen.findByRole('button', { name: 'Turn off' }));
    await user.click(screen.getByRole('button', { name: 'Keep it on' }));

    expect(screen.getByText('On')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Turn off' })).toBeInTheDocument();
  });

  it('sends the plan and the new contribution as cents, and shows what came back', async () => {
    const user = userEvent.setup();
    mount(makeMandate({ contribution_cents: 2500 }));
    const bodies = recordPatches(makeMandate({ contribution_cents: 0 }));

    await user.click(await screen.findByRole('button', { name: 'Change contribution' }));
    await user.click(screen.getByRole('radio', { name: /No thank you/ }));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(bodies).toEqual([{ plan: 'annual', contribution_cents: 0 }]));
  });

  it('opens the change form with the tier the mandate already carries', async () => {
    const user = userEvent.setup();
    mount(makeMandate({ contribution_cents: 2500 }));

    await user.click(await screen.findByRole('button', { name: 'Change contribution' }));

    expect(screen.getByRole('radio', { name: /Supporter/ })).toBeChecked();
    expect(screen.getByRole('radio', { name: /Annual/ })).toBeChecked();
  });

  it('sends a contribution that is not whole dollars back untouched', async () => {
    const user = userEvent.setup();
    mount(makeMandate({ contribution_cents: 2550 }));
    const bodies = recordPatches(makeMandate({ contribution_cents: 2550 }));

    await user.click(await screen.findByRole('button', { name: 'Change contribution' }));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(bodies).toEqual([{ plan: 'annual', contribution_cents: 2550 }]));
  });

  it('shows an amount no tier matches in the box that can edit it', async () => {
    const user = userEvent.setup();
    mount(makeMandate({ contribution_cents: 7500 }));

    await user.click(await screen.findByRole('button', { name: 'Change contribution' }));

    expect(screen.getByRole('radio', { name: 'Other amount' })).toBeChecked();
    expect(screen.getByLabelText('Contribution amount')).toHaveValue('75');
  });

  it('offers no plan that never expires in the change form', async () => {
    const user = userEvent.setup();
    mount(makeMandate());

    await user.click(await screen.findByRole('button', { name: 'Change contribution' }));

    expect(screen.queryByRole('radio', { name: /Life/ })).not.toBeInTheDocument();
  });

  it('never reads a failed renewal call as renewal being off', async () => {
    mountUnreadable();

    expect(await screen.findByText('Your renewal settings could not be read')).toBeInTheDocument();
    expect(screen.queryByText('Off')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Turn on' })).not.toBeInTheDocument();
  });

  it('confirms the SetupIntent a redirecting method came back with', async () => {
    const confirms: unknown[] = [];
    server.use(
      http.post(`${API}/me/renewal/confirm`, async ({ request }) => {
        confirms.push(await request.json());
        return HttpResponse.json({ mandate: makeMandate() } satisfies RenewalEnvelope);
      }),
    );
    mount(makeMandate({ status: 'pending' }), {
      route: '/payments?setup_intent=seti_redirected&redirect_status=succeeded',
    });

    await waitFor(() =>
      expect(confirms).toEqual([{ setup_intent_id: 'seti_redirected', setup_token: '' }]),
    );
    expect(await screen.findByText('On')).toBeInTheDocument();
  });

  it('says so when the SetupIntent it came back with is refused', async () => {
    server.use(
      http.post(`${API}/me/renewal/confirm`, () =>
        HttpResponse.json({ detail: 'That setup was never completed.' }, { status: 400 }),
      ),
    );
    mount(makeMandate({ status: 'pending' }), {
      route: '/payments?setup_intent=seti_abandoned',
    });

    expect(await screen.findByRole('alert')).toHaveTextContent('That setup was never completed.');
  });

  it('puts a refused contribution back on the field it belongs to', async () => {
    const user = userEvent.setup();
    mount(makeMandate());
    server.use(
      http.patch(`${API}/me/renewal`, () =>
        HttpResponse.json(
          { contribution_cents: ['That is more than we can take.'] },
          { status: 400 },
        ),
      ),
    );

    await user.click(await screen.findByRole('button', { name: 'Change contribution' }));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('That is more than we can take.');
  });

  describe('for a life member', () => {
    const lifetime = { membership: LIFETIME_MEMBERSHIP };

    it('is headed Automatic contribution, because nothing of theirs renews', async () => {
      mount(null, lifetime);

      expect(
        await screen.findByRole('heading', { name: 'Automatic contribution' }),
      ).toBeInTheDocument();
    });

    it('offers to charge the contribution once a year when there is no mandate', async () => {
      mount(null, lifetime);

      expect(
        await screen.findByText(
          /CalDART will charge a saved card or PayPal account once a year for the contribution you choose\./,
        ),
      ).toBeInTheDocument();
    });

    it('names the amount and the date of the next contribution', async () => {
      mount(makeContributionMandate({ next_charge_on: '2027-08-20' }), lifetime);

      expect(await screen.findByText('Next charge')).toBeInTheDocument();
      expect(screen.getByText('Next charge').nextElementSibling).toHaveTextContent(
        '2027/08/20 · $50.00',
      );
    });

    it('names the contribution rather than a plan it does not renew', async () => {
      mount(makeContributionMandate(), lifetime);

      expect(await screen.findByText('Contribution charged each year')).toBeInTheDocument();
      expect(screen.queryByText('Plan')).not.toBeInTheDocument();
    });

    it('says the contribution stopped, not the renewal, when the charge was refused', async () => {
      mount(
        makeContributionMandate({ status: 'paused', last_error: 'Your card was declined' }),
        lifetime,
      );

      expect(await screen.findByText(/Automatic contribution stopped/)).toBeInTheDocument();
    });

    it('changes the contribution without naming a plan', async () => {
      const user = userEvent.setup();
      mount(makeContributionMandate(), lifetime);
      const bodies = recordPatches(makeContributionMandate({ contribution_cents: 2500 }));

      await user.click(await screen.findByRole('button', { name: 'Change contribution' }));
      expect(screen.queryByRole('radio', { name: /Annual/ })).not.toBeInTheDocument();
      await user.click(screen.getByRole('radio', { name: /Supporter/ }));
      await user.click(screen.getByRole('button', { name: 'Save changes' }));

      await waitFor(() => expect(bodies).toEqual([{ contribution_cents: 2500 }]));
    });

    it('names no plan even when the membership could not be read', async () => {
      const user = userEvent.setup();
      mount(makeContributionMandate(), { ...lifetime, hasMembership: false });
      const bodies = recordPatches(makeContributionMandate());

      await user.click(await screen.findByRole('button', { name: 'Change contribution' }));
      await user.click(screen.getByRole('radio', { name: /Supporter/ }));
      await user.click(screen.getByRole('button', { name: 'Save changes' }));

      await waitFor(() => expect(bodies).toEqual([{ contribution_cents: 2500 }]));
    });

    it('will not save an authority with nothing to charge', async () => {
      const user = userEvent.setup();
      mount(makeContributionMandate(), lifetime);

      await user.click(await screen.findByRole('button', { name: 'Change contribution' }));
      await user.click(screen.getByRole('radio', { name: /No thank you/ }));

      expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();
      expect(screen.getByText('Choose a contribution to charge each year.')).toBeVisible();
    });

    it('reports the contribution, not the renewal, when it is turned off', async () => {
      const user = userEvent.setup();
      mount(makeContributionMandate(), lifetime);
      server.use(http.delete(`${API}/me/renewal`, () => new HttpResponse(null, { status: 204 })));

      await user.click(await screen.findByRole('button', { name: 'Turn off' }));
      await user.click(screen.getByRole('button', { name: 'Yes, turn it off' }));

      expect(await screen.findByText('Automatic contribution is off.')).toBeInTheDocument();
    });
  });
});
