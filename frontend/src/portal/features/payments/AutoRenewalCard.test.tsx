/**
 * The Automatic renewal card, one test per state the mandate can be in.
 *
 * The card is the only thing on the screen that says whether CalDART is going
 * to take money, so each state is checked for the sentence that answers that
 * and for the control that changes it.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import type { RenewalEnvelope, RenewalMandate } from '@/portal/api/types';
import { makeMandate, makePaymentsConfig } from '@test/fixtures/payments';
import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { AutoRenewalCard } from './AutoRenewalCard';

/** Serve `GET /me/renewal` with `mandate` and render the card at `route`. */
function mount(mandate: RenewalMandate | null, { route = '/payments' }: { route?: string } = {}) {
  server.use(
    signedInAs(makeUser()),
    http.get(`${API}/me/renewal`, () => HttpResponse.json({ mandate } satisfies RenewalEnvelope)),
    http.get(`${API}/payments/config`, () => HttpResponse.json(makePaymentsConfig())),
  );
  return renderWithProviders(<AutoRenewalCard />, { route });
}

/** Render the card with `GET /me/renewal` failing outright. */
function mountUnreadable() {
  server.use(
    signedInAs(makeUser()),
    http.get(`${API}/me/renewal`, () =>
      HttpResponse.json({ detail: 'Server error.' }, { status: 500 }),
    ),
  );
  return renderWithProviders(<AutoRenewalCard />, { route: '/payments' });
}

describe('AutoRenewalCard', () => {
  it('offers to turn renewal on when the member has never had a mandate', async () => {
    mount(null);

    expect(await screen.findByText('Off')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Turn on' })).toBeInTheDocument();
  });

  it('treats an unfinished setup as off, so the only way forward is to start again', async () => {
    mount(makeMandate({ status: 'pending', next_charge_on: null }));

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

  it('gives the reason the last charge was refused when the mandate is paused', async () => {
    mount(
      makeMandate({
        status: 'paused',
        failure_count: 3,
        last_error: 'Your card was declined',
        next_charge_on: null,
      }),
    );

    expect(await screen.findByText('Stopped')).toBeInTheDocument();
    expect(screen.getByText(/Your card was declined/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Turn on again' })).toBeInTheDocument();
  });

  it('says when a canceled mandate was turned off', async () => {
    mount(
      makeMandate({
        status: 'canceled',
        canceled_at: '2026-05-04T10:00:00Z',
        next_charge_on: null,
      }),
    );

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

  it('sends the new contribution as cents and shows what came back', async () => {
    const user = userEvent.setup();
    mount(makeMandate({ contribution_cents: 2500 }));
    const bodies: { contribution_cents: number }[] = [];
    server.use(
      http.patch(`${API}/me/renewal`, async ({ request }) => {
        const body = (await request.json()) as { contribution_cents: number };
        bodies.push(body);
        return HttpResponse.json({
          mandate: makeMandate({ contribution_cents: body.contribution_cents }),
        } satisfies RenewalEnvelope);
      }),
    );

    await user.click(await screen.findByRole('button', { name: 'Change contribution' }));
    const box = screen.getByLabelText('Contribution renewed each year');
    await user.clear(box);
    await user.type(box, '40');
    await user.click(screen.getByRole('button', { name: 'Save contribution' }));

    await waitFor(() => expect(bodies).toEqual([{ contribution_cents: 4000 }]));
  });

  it('never reads a failed renewal call as renewal being off', async () => {
    mountUnreadable();

    expect(await screen.findByText('Your renewal settings could not be read')).toBeInTheDocument();
    expect(screen.queryByText('Off')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Turn on' })).not.toBeInTheDocument();
  });

  it('sends a contribution that is not whole dollars back untouched', async () => {
    const user = userEvent.setup();
    mount(makeMandate({ contribution_cents: 2550 }));
    const bodies: { contribution_cents: number }[] = [];
    server.use(
      http.patch(`${API}/me/renewal`, async ({ request }) => {
        bodies.push((await request.json()) as { contribution_cents: number });
        return HttpResponse.json({ mandate: makeMandate() } satisfies RenewalEnvelope);
      }),
    );

    await user.click(await screen.findByRole('button', { name: 'Change contribution' }));
    await user.click(screen.getByRole('button', { name: 'Save contribution' }));

    await waitFor(() => expect(bodies).toEqual([{ contribution_cents: 2550 }]));
  });

  it('confirms the SetupIntent a redirecting method came back with', async () => {
    const confirms: unknown[] = [];
    server.use(
      http.post(`${API}/me/renewal/confirm`, async ({ request }) => {
        confirms.push(await request.json());
        return HttpResponse.json({ mandate: makeMandate() } satisfies RenewalEnvelope);
      }),
    );
    mount(makeMandate({ status: 'pending', next_charge_on: null }), {
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
    mount(makeMandate({ status: 'pending', next_charge_on: null }), {
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
          {
            status: 400,
          },
        ),
      ),
    );

    await user.click(await screen.findByRole('button', { name: 'Change contribution' }));
    await user.click(screen.getByRole('button', { name: 'Save contribution' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('That is more than we can take.');
  });
});
