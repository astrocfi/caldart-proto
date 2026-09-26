import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import type { DonationCheckoutRequest, DonationsConfig } from '@/portal/api/types';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { DonationForm } from './DonationForm';

const CONFIG_URL = `${API}/donations/config`;
const RETURN_URL = '/donate/';
const TOKEN = 'signed-token';

const CONFIG: DonationsConfig = {
  providers: ['mock'],
  stripe_publishable_key: '',
  paypal_client_id: '',
  contribution_tiers: [
    { label: 'No contribution', cents: 0 },
    { label: 'Participating', cents: 2000 },
    { label: 'Bronze', cents: 10000 },
  ],
  max_contribution_cents: 9_999_900,
  counties: ['Alameda', 'Marin'],
  darts: [{ id: 4, name: 'Bay Area' }],
  states: [
    { value: 'CA', label: 'California' },
    { value: 'NV', label: 'Nevada' },
  ],
};

interface Served {
  checkouts: DonationCheckoutRequest[];
  completions: Record<string, unknown>[];
}

/** Serve the config and a mock gift that succeeds, recording what was sent. */
function serveGift(): Served {
  const served: Served = { checkouts: [], completions: [] };
  server.use(
    http.get(CONFIG_URL, () => HttpResponse.json(CONFIG)),
    http.post(`${API}/donations/checkout`, async ({ request }) => {
      served.checkouts.push((await request.json()) as DonationCheckoutRequest);
      return HttpResponse.json(
        { payment_id: 12, provider: 'mock', client: {}, token: TOKEN },
        { status: 201 },
      );
    }),
    http.post(`${API}/donations/mock/complete`, async ({ request }) => {
      served.completions.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({ status: 'succeeded', membership: null });
    }),
  );
  return served;
}

function renderForm(handleGiven = vi.fn(), search = '') {
  return renderWithProviders(
    <DonationForm
      configUrl={CONFIG_URL}
      returnUrl={RETURN_URL}
      onGiven={handleGiven}
      search={search}
    />,
  );
}

/** Choose $100 and fill in the four required fields. */
async function fillInGift(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('radio', { name: /Bronze/ }));
  await user.type(screen.getByLabelText(/First name/), 'Pat');
  await user.type(screen.getByLabelText(/Last name/), 'Giver');
  await user.type(screen.getByLabelText(/^Email/), 'pat@example.org');
  await user.type(screen.getByLabelText(/^Phone/), '4155550100');
}

describe('DonationForm', () => {
  it('offers every tier but the one that gives nothing', async () => {
    serveGift();
    renderForm();

    await screen.findByRole('radio', { name: /Bronze/ });

    expect(screen.queryByRole('radio', { name: /No thank you/ })).not.toBeInTheDocument();
  });

  it('names the amount fieldset Amount', async () => {
    serveGift();
    renderForm();

    expect(await screen.findByRole('group', { name: 'Amount' })).toBeInTheDocument();
  });

  it('refuses to continue without an amount', async () => {
    serveGift();
    const user = userEvent.setup();
    renderForm();

    await user.click(await screen.findByRole('button', { name: 'Continue to payment' }));

    expect(screen.getByText('Choose an amount to give.')).toBeInTheDocument();
  });

  it('refuses to continue without a ten-digit phone number', async () => {
    serveGift();
    const user = userEvent.setup();
    renderForm();
    await fillInGift(user);
    await user.clear(screen.getByLabelText(/^Phone/));
    await user.type(screen.getByLabelText(/^Phone/), '555');

    await user.click(screen.getByRole('button', { name: 'Continue to payment' }));

    expect(screen.getByText('Use a ten-digit number like 415-555-0100.')).toBeInTheDocument();
  });

  it('keeps the optional section closed until it is opened', async () => {
    serveGift();
    renderForm();

    await screen.findByRole('radio', { name: /Bronze/ });

    expect(screen.getByText('Tell us more (optional)').closest('details')).not.toHaveAttribute(
      'open',
    );
  });

  it('shows what is being given before the payment', async () => {
    serveGift();
    const user = userEvent.setup();
    renderForm();
    await fillInGift(user);

    await user.click(screen.getByRole('button', { name: 'Continue to payment' }));

    expect(screen.getByText(/You are giving/)).toHaveTextContent(
      'You are giving $100.00 as Pat Giver (pat@example.org).',
    );
  });

  it('goes back to the details, as they were, from Change', async () => {
    serveGift();
    const user = userEvent.setup();
    renderForm();
    await fillInGift(user);
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }));

    await user.click(screen.getByRole('button', { name: 'Change' }));

    expect(screen.getByLabelText(/First name/)).toHaveValue('Pat');
  });

  it('starts the gift with the giver and the amount', async () => {
    const served = serveGift();
    const user = userEvent.setup();
    renderForm();
    await fillInGift(user);
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }));

    await user.click(await screen.findByRole('button', { name: 'Succeed' }));

    await waitFor(() =>
      expect(served.checkouts).toEqual([
        {
          first_name: 'Pat',
          last_name: 'Giver',
          email: 'pat@example.org',
          phone: '415-555-0100',
          contribution_cents: 10000,
          provider: 'mock',
        },
      ]),
    );
  });

  it('sends what the giver told us in the optional section', async () => {
    const served = serveGift();
    const user = userEvent.setup();
    renderForm();
    await fillInGift(user);
    await user.click(screen.getByText('Tell us more (optional)'));
    await user.selectOptions(screen.getByLabelText('California county'), 'Marin');
    await user.selectOptions(screen.getByLabelText('DART'), 'Bay Area');
    await user.click(screen.getByLabelText('Fundraising'));
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }));

    await user.click(await screen.findByRole('button', { name: 'Succeed' }));

    await waitFor(() =>
      expect(served.checkouts[0]).toMatchObject({
        county: 'Marin',
        dart_id: 4,
        vol_fundraising: true,
      }),
    );
  });

  it('finishes the gift with the token the checkout answered', async () => {
    const served = serveGift();
    const user = userEvent.setup();
    renderForm();
    await fillInGift(user);
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }));

    await user.click(await screen.findByRole('button', { name: 'Succeed' }));

    await waitFor(() =>
      expect(served.completions).toEqual([{ payment_id: 12, outcome: 'succeed', token: TOKEN }]),
    );
  });

  it('says where the receipt went once the gift has gone through', async () => {
    serveGift();
    const user = userEvent.setup();
    renderForm();
    await fillInGift(user);
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }));

    await user.click(await screen.findByRole('button', { name: 'Succeed' }));

    expect(
      await screen.findByText('A receipt is on its way to pat@example.org.'),
    ).toBeInTheDocument();
  });

  it('lets the page show its thanks once the gift has gone through', async () => {
    serveGift();
    const onGiven = vi.fn();
    const user = userEvent.setup();
    renderForm(onGiven);
    await fillInGift(user);
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }));

    await user.click(await screen.findByRole('button', { name: 'Succeed' }));

    await waitFor(() => expect(onGiven).toHaveBeenCalledTimes(1));
  });

  it('shows why an address that belongs to a member is refused beside the field', async () => {
    serveGift();
    server.use(
      http.post(`${API}/donations/checkout`, () =>
        HttpResponse.json(
          {
            email: ['An account already uses that email address. Sign in to donate.'],
            code: 'has_account',
          },
          { status: 400 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderForm();
    await fillInGift(user);
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }));

    await user.click(await screen.findByRole('button', { name: 'Succeed' }));

    // The refusal takes the giver back to the details, with the message beside
    // the field it named rather than only in the payment panel.
    const email = await screen.findByLabelText(/^Email/);
    expect(email).toHaveAccessibleDescription(
      'An account already uses that email address. Sign in to donate. Your receipt goes here',
    );
    expect(screen.getByRole('button', { name: 'Continue to payment' })).toBeInTheDocument();
  });

  it('keeps what was typed when a field refusal sends the giver back', async () => {
    serveGift();
    server.use(
      http.post(`${API}/donations/checkout`, () =>
        HttpResponse.json({ phone: ['Use a ten-digit number.'] }, { status: 400 }),
      ),
    );
    const user = userEvent.setup();
    renderForm();
    await fillInGift(user);
    await user.click(screen.getByRole('button', { name: 'Continue to payment' }));

    await user.click(await screen.findByRole('button', { name: 'Succeed' }));

    await screen.findByRole('button', { name: 'Continue to payment' });
    expect(screen.getByLabelText(/^Email/)).toHaveValue('pat@example.org');
  });

  it('confirms a gift a redirect brought back, with its token', async () => {
    let sent: Record<string, unknown> | null = null;
    server.use(
      http.post(`${API}/donations/stripe/confirm`, async ({ request }) => {
        sent = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ status: 'succeeded', membership: null });
      }),
    );
    renderForm(vi.fn(), `?payment_id=12&token=${TOKEN}&payment_intent=pi_1`);

    await screen.findByText('A receipt is on its way to your email address.');

    expect(sent).toEqual({ payment_id: 12, payment_intent_id: 'pi_1', token: TOKEN });
  });
});
