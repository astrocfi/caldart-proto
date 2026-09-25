/**
 * The inline flow that saves a payment method without charging it.
 *
 * Stripe's Payment Element and PayPal's buttons are stubbed, exactly as the
 * checkout's own suite stubs them: what matters here is the plan, contribution
 * and provider our own server is asked for, and what the member is told.
 */
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import type { RenewalEnvelope, RenewalSetupRequest } from '@/portal/api/types';
import { makeMandate, makePaymentsConfig } from '@test/fixtures/payments';
import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { RenewalSetup } from './RenewalSetup';

const confirmSetup = vi.fn();

vi.mock('@stripe/stripe-js', () => ({
  loadStripe: () => Promise.resolve({ id: 'stripe-stub' }),
}));

vi.mock('@stripe/react-stripe-js', () => ({
  Elements: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PaymentElement: () => <div data-testid="payment-element">Payment element</div>,
  useStripe: () => ({ confirmSetup }),
  useElements: () => ({}),
}));

vi.mock('@paypal/react-paypal-js', () => ({
  PayPalScriptProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PayPalButtons: ({
    createVaultSetupToken,
    onApprove,
  }: {
    createVaultSetupToken: () => Promise<string>;
    onApprove: (data: { orderID: string }) => Promise<void>;
  }) => (
    <button
      type="button"
      onClick={() => {
        void (async () => {
          await createVaultSetupToken();
          await onApprove({ orderID: '' });
        })();
      }}
    >
      Save with PayPal
    </button>
  ),
}));

/** Serve the config and record every setup request the flow sends. */
function mount({
  providers,
  isLifetime = false,
}: {
  providers: ('stripe' | 'paypal' | 'mock')[];
  isLifetime?: boolean;
}) {
  const setups: RenewalSetupRequest[] = [];
  const confirms: unknown[] = [];
  server.use(
    signedInAs(makeUser()),
    http.get(`${API}/payments/config`, () => HttpResponse.json(makePaymentsConfig({ providers }))),
    http.post(`${API}/me/renewal/setup`, async ({ request }) => {
      const body = (await request.json()) as RenewalSetupRequest;
      setups.push(body);
      return HttpResponse.json({
        provider: body.provider,
        client:
          body.provider === 'stripe'
            ? { client_secret: 'seti_secret' }
            : body.provider === 'paypal'
              ? { setup_token: 'vault-token' }
              : {},
      });
    }),
    http.post(`${API}/me/renewal/confirm`, async ({ request }) => {
      confirms.push(await request.json());
      return HttpResponse.json({ mandate: makeMandate() } satisfies RenewalEnvelope);
    }),
  );
  const handleDone = vi.fn();
  const handleCancel = vi.fn();
  renderWithProviders(
    <RenewalSetup isLifetime={isLifetime} onCancel={handleCancel} onDone={handleDone} />,
    { route: '/payments' },
  );
  return { setups, confirms, handleDone, handleCancel };
}

describe('RenewalSetup', () => {
  it('offers only the plans that have a term, because a life membership never renews', async () => {
    mount({ providers: ['mock'] });

    expect(await screen.findByRole('radio', { name: /Annual/ })).toBeInTheDocument();
    expect(screen.queryByRole('radio', { name: /Life/ })).not.toBeInTheDocument();
  });

  it('states what the yearly charge will come to, plan plus contribution', async () => {
    const user = userEvent.setup();
    mount({ providers: ['mock'] });

    await user.click(await screen.findByRole('radio', { name: /Supporter/ }));

    expect(screen.getByText('$70.00')).toBeInTheDocument();
  });

  it('saves the mock method with the chosen plan and contribution', async () => {
    const user = userEvent.setup();
    const { setups, confirms, handleDone } = mount({ providers: ['mock'] });

    await user.click(await screen.findByRole('radio', { name: /Supporter/ }));
    await user.click(screen.getByRole('button', { name: 'Save this test card' }));

    await waitFor(() => expect(handleDone).toHaveBeenCalledOnce());
    expect(setups).toEqual([{ plan: 'annual', contribution_cents: 2500, provider: 'mock' }]);
    expect(confirms).toEqual([{ setup_intent_id: '', setup_token: '' }]);
  });

  it('confirms a Stripe SetupIntent with the id Stripe answered with', async () => {
    const user = userEvent.setup();
    confirmSetup.mockResolvedValue({ setupIntent: { id: 'seti_123' } });
    const { setups, confirms, handleDone } = mount({ providers: ['stripe'] });

    expect(await screen.findByTestId('payment-element')).toBeInTheDocument();
    expect(setups).toEqual([{ plan: 'annual', contribution_cents: 0, provider: 'stripe' }]);

    await user.click(screen.getByRole('button', { name: 'Save this card' }));

    await waitFor(() => expect(handleDone).toHaveBeenCalledOnce());
    expect(confirms).toEqual([{ setup_intent_id: 'seti_123', setup_token: '' }]);
  });

  it('shows what Stripe refused a card for and saves nothing', async () => {
    const user = userEvent.setup();
    confirmSetup.mockResolvedValue({ error: { message: 'Your card was declined.' } });
    const { confirms, handleDone } = mount({ providers: ['stripe'] });

    await user.click(await screen.findByRole('button', { name: 'Save this card' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Your card was declined.');
    expect(confirms).toEqual([]);
    expect(handleDone).not.toHaveBeenCalled();
  });

  it('confirms PayPal with the setup token the server issued', async () => {
    const user = userEvent.setup();
    const { confirms, handleDone } = mount({ providers: ['paypal'] });

    await user.click(await screen.findByRole('button', { name: 'Save with PayPal' }));

    await waitFor(() => expect(handleDone).toHaveBeenCalledOnce());
    expect(confirms).toEqual([{ setup_intent_id: '', setup_token: 'vault-token' }]);
  });

  it('puts the server refusal on screen rather than a generic notice', async () => {
    const user = userEvent.setup();
    const { handleDone } = mount({ providers: ['mock'] });
    server.use(
      http.post(`${API}/me/renewal/setup`, () =>
        HttpResponse.json({ auto_renew: ['That plan never expires.'] }, { status: 400 }),
      ),
    );

    await user.click(await screen.findByRole('button', { name: 'Save this test card' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('That plan never expires.');
    expect(handleDone).not.toHaveBeenCalled();
  });

  it('promises the warning email in the words the card uses', async () => {
    mount({ providers: ['mock'] });

    expect(
      await screen.findByText(/We will email you fourteen days before every charge\./),
    ).toBeInTheDocument();
  });

  it('hands the flow back unchanged when the member cancels', async () => {
    const user = userEvent.setup();
    const { handleCancel } = mount({ providers: ['mock'] });

    await user.click(await screen.findByRole('button', { name: 'Cancel' }));

    expect(handleCancel).toHaveBeenCalledOnce();
  });

  describe('for a life member', () => {
    it('offers no plan, because their membership never runs out', async () => {
      mount({ providers: ['mock'], isLifetime: true });

      expect(await screen.findByRole('radio', { name: /Supporter/ })).toBeInTheDocument();
      expect(screen.queryByRole('radio', { name: /Annual/ })).not.toBeInTheDocument();
    });

    it('states that the yearly charge is the contribution alone', async () => {
      const user = userEvent.setup();
      mount({ providers: ['mock'], isLifetime: true });

      await user.click(await screen.findByRole('radio', { name: /Supporter/ }));

      expect(screen.getByText(/Each year CalDART will charge/)).toHaveTextContent(
        'Each year CalDART will charge $25.00 for your contribution.',
      );
    });

    it('asks for a contribution before it offers to save a method', async () => {
      mount({ providers: ['mock'], isLifetime: true });

      expect(await screen.findByText('Choose a contribution to charge each year.')).toBeVisible();
      expect(screen.queryByRole('button', { name: 'Save this test card' })).not.toBeInTheDocument();
    });

    it('saves the method with no plan once an amount is chosen', async () => {
      const user = userEvent.setup();
      const { setups, handleDone } = mount({ providers: ['mock'], isLifetime: true });

      await user.click(await screen.findByRole('radio', { name: /Supporter/ }));
      await user.click(screen.getByRole('button', { name: 'Save this test card' }));

      await waitFor(() => expect(handleDone).toHaveBeenCalledOnce());
      expect(setups).toEqual([{ contribution_cents: 2500, provider: 'mock' }]);
    });
  });
});
