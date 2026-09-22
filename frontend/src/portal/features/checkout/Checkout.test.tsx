import { QueryClient } from '@tanstack/react-query';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { CheckoutRequest, PaymentsConfig } from '../../api/types';
import { API, CURRENT_MEMBERSHIP, NO_MEMBERSHIP, makeUser } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { AUTH_ME_KEY } from '../../auth/useAuth';
import { Checkout } from './Checkout';

/* --------------------------------------------------------- stripe & paypal */
const confirmPayment = vi.fn();

vi.mock('@stripe/stripe-js', () => ({
  loadStripe: () => Promise.resolve({ id: 'stripe-stub' }),
}));

vi.mock('@stripe/react-stripe-js', () => ({
  Elements: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PaymentElement: () => <div data-testid="payment-element">Payment element</div>,
  useStripe: () => ({ confirmPayment }),
  useElements: () => ({}),
}));

vi.mock('@paypal/react-paypal-js', () => ({
  PayPalScriptProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PayPalButtons: ({
    createOrder,
    onApprove,
    onCancel,
    onError,
  }: {
    createOrder: () => Promise<string>;
    onApprove: (data: { orderID: string }) => Promise<void>;
    onCancel: () => void;
    onError: (error: unknown) => void;
  }) => (
    <>
      <button
        type="button"
        onClick={() => {
          void (async () => {
            try {
              const orderId = await createOrder();
              await onApprove({ orderID: orderId });
            } catch (caught) {
              // The SDK absorbs a `createOrder` rejection and hands it to `onError`,
              // so the panel's own handler runs right after its catch block.
              onError(caught);
            }
          })();
        }}
      >
        Pay with PayPal
      </button>
      <button type="button" onClick={onCancel}>
        Close the PayPal window
      </button>
      <button type="button" onClick={() => onError(new Error('the SDK never loaded'))}>
        Break the PayPal window
      </button>
    </>
  ),
}));

/* ------------------------------------------------------------------ config */
const PLANS: PaymentsConfig['plans'] = [
  {
    slug: 'annual',
    name: 'Annual',
    price_cents: 4500,
    duration_days: 365,
    description: 'Membership for one year.',
  },
  {
    slug: 'life',
    name: 'Life',
    price_cents: 65000,
    duration_days: null,
    description: 'One payment, for life.',
  },
];

const TIERS: PaymentsConfig['contribution_tiers'] = [
  { label: 'No contribution', cents: 0 },
  { label: 'Participating', cents: 2000 },
  { label: 'Bronze', cents: 10000 },
];

function config(overrides: Partial<PaymentsConfig> = {}): PaymentsConfig {
  return {
    providers: ['mock'],
    stripe_publishable_key: '',
    paypal_client_id: '',
    plans: PLANS,
    contribution_tiers: TIERS,
    ...overrides,
  };
}

function serveConfig(value: PaymentsConfig) {
  server.use(http.get(`${API}/payments/config`, () => HttpResponse.json(value)));
}

/** Record every checkout request so the tests can assert on the amounts sent. */
function serveCheckout(client: Record<string, string> = {}) {
  const requests: CheckoutRequest[] = [];
  server.use(
    http.post(`${API}/payments/checkout`, async ({ request }) => {
      const body = (await request.json()) as CheckoutRequest;
      requests.push(body);
      return HttpResponse.json(
        { payment_id: 77, provider: body.provider, client },
        { status: 201 },
      );
    }),
  );
  return requests;
}

beforeEach(() => {
  confirmPayment.mockReset();
});

describe('Checkout', () => {
  it('offers every plan and defaults to Annual', async () => {
    serveConfig(config());
    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);

    expect(await screen.findByRole('radio', { name: /Annual/ })).toBeChecked();
    expect(screen.getByRole('radio', { name: /Life/ })).not.toBeChecked();
    expect(screen.getByTestId('checkout-total')).toHaveTextContent('$45.00');
  });

  it('selects the first plan offered when there is no annual plan', async () => {
    serveConfig(config({ plans: [PLANS[1]!] }));
    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);

    expect(await screen.findByRole('radio', { name: /Life/ })).toBeChecked();
  });

  it('pays for the first plan offered when there is no annual plan', async () => {
    const user = userEvent.setup();
    serveConfig(config({ plans: [PLANS[1]!] }));
    const requests = serveCheckout();
    server.use(
      http.post(`${API}/payments/mock/complete`, () =>
        HttpResponse.json({ status: 'succeeded', membership: CURRENT_MEMBERSHIP }),
      ),
    );

    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);
    await user.click(await screen.findByRole('button', { name: 'Succeed' }));

    await waitFor(() => expect(requests).toEqual([expect.objectContaining({ plan: 'life' })]));
  });

  it('renewals are labeled as renewals', async () => {
    serveConfig(config());
    renderWithProviders(<Checkout mode="renew" onSuccess={vi.fn()} />);
    expect(await screen.findByText('Renew your membership')).toBeInTheDocument();
    expect(screen.getByText('Renewal')).toBeInTheDocument();
  });

  it('updates the live total when the plan changes', async () => {
    const user = userEvent.setup();
    serveConfig(config());
    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);

    await user.click(await screen.findByRole('radio', { name: /Life/ }));
    expect(screen.getByTestId('checkout-total')).toHaveTextContent('$650.00');
  });

  it('adds a contribution tier to the total', async () => {
    const user = userEvent.setup();
    serveConfig(config());
    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);

    await user.click(await screen.findByRole('radio', { name: /Bronze/ }));
    expect(screen.getByTestId('checkout-total')).toHaveTextContent('$145.00');
    expect(screen.getByText('Contribution')).toBeInTheDocument();
  });

  it('accepts an "other amount" contribution', async () => {
    const user = userEvent.setup();
    serveConfig(config());
    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);

    await user.click(await screen.findByRole('radio', { name: 'Other amount' }));
    await user.type(screen.getByLabelText('Contribution amount'), '7');
    expect(screen.getByTestId('checkout-total')).toHaveTextContent('$52.00');
  });

  it('offers "No thank you" for the zero tier', async () => {
    serveConfig(config());
    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);
    expect(await screen.findByRole('radio', { name: 'No thank you' })).toBeChecked();
  });

  it('only shows tabs for the configured providers', async () => {
    serveConfig(config({ providers: ['mock'] }));
    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);

    expect(await screen.findByRole('tab', { name: 'Test payment' })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: /Card/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'PayPal' })).not.toBeInTheDocument();
  });

  it('shows all three tabs when everything is configured', async () => {
    serveConfig(
      config({
        providers: ['stripe', 'paypal', 'mock'],
        stripe_publishable_key: 'pk_test',
        paypal_client_id: 'paypal-id',
      }),
    );
    serveCheckout({ client_secret: 'pi_1_secret' });
    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);

    const tabs = await screen.findAllByRole('tab');
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      'Card · Apple Pay · Google Pay',
      'PayPal',
      'Test payment',
    ]);
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true');
  });

  it('says so when no provider is configured', async () => {
    serveConfig(config({ providers: [] }));
    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);
    expect(await screen.findByText('Online payment is not set up yet')).toBeInTheDocument();
  });

  it('reports a broken config endpoint', async () => {
    server.use(
      http.get(`${API}/payments/config`, () =>
        HttpResponse.json({ detail: 'Boom' }, { status: 500 }),
      ),
    );
    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);
    expect(await screen.findByText('Payment options could not be loaded')).toBeInTheDocument();
  });

  it('moves between tabs with the arrow keys', async () => {
    const user = userEvent.setup();
    serveConfig(config({ providers: ['paypal', 'mock'], paypal_client_id: 'paypal-id' }));
    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);

    const paypalTab = await screen.findByRole('tab', { name: 'PayPal' });
    paypalTab.focus();
    await user.keyboard('{ArrowRight}');

    expect(screen.getByRole('tab', { name: 'Test payment' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });
});

describe('Checkout · mock provider', () => {
  it('runs a payment end to end and reports the new membership', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    serveConfig(config());
    const requests = serveCheckout();
    server.use(
      http.post(`${API}/payments/mock/complete`, () =>
        HttpResponse.json({ status: 'succeeded', membership: CURRENT_MEMBERSHIP }),
      ),
    );

    renderWithProviders(<Checkout mode="join" onSuccess={onSuccess} />);
    await user.click(await screen.findByRole('radio', { name: /Participating/ }));
    await user.click(screen.getByRole('button', { name: 'Succeed' }));

    await waitFor(() =>
      expect(onSuccess).toHaveBeenCalledWith({ paymentId: 77, membership: CURRENT_MEMBERSHIP }),
    );
    expect(requests).toEqual([{ plan: 'annual', contribution_cents: 2000, provider: 'mock' }]);
  });

  it('reports a declined test payment without calling onSuccess', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    serveConfig(config());
    serveCheckout();
    server.use(
      http.post(`${API}/payments/mock/complete`, () =>
        HttpResponse.json({ status: 'failed', membership: NO_MEMBERSHIP }),
      ),
    );

    renderWithProviders(<Checkout mode="join" onSuccess={onSuccess} />);
    await user.click(await screen.findByRole('button', { name: 'Fail' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('declined');
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it('surfaces an API error', async () => {
    const user = userEvent.setup();
    serveConfig(config());
    server.use(
      http.post(`${API}/payments/checkout`, () =>
        HttpResponse.json({ detail: 'That plan is closed.' }, { status: 400 }),
      ),
    );

    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);
    await user.click(await screen.findByRole('button', { name: 'Succeed' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('That plan is closed.');
  });
});

describe('Checkout · Stripe', () => {
  const stripeConfig = config({
    providers: ['stripe', 'mock'],
    stripe_publishable_key: 'pk_test_123',
  });

  it('creates a payment intent when the tab opens and mounts the element', async () => {
    serveConfig(stripeConfig);
    const requests = serveCheckout({ client_secret: 'pi_1_secret_abc' });

    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);

    expect(await screen.findByTestId('payment-element')).toBeInTheDocument();
    expect(requests).toEqual([{ plan: 'annual', contribution_cents: 0, provider: 'stripe' }]);
    expect(screen.getByRole('button', { name: 'Pay $45.00' })).toBeInTheDocument();
  });

  it('confirms with our server after Stripe succeeds', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    serveConfig(stripeConfig);
    serveCheckout({ client_secret: 'pi_1_secret_abc' });
    confirmPayment.mockResolvedValue({ paymentIntent: { id: 'pi_1', status: 'succeeded' } });

    const confirmations: unknown[] = [];
    server.use(
      http.post(`${API}/payments/stripe/confirm`, async ({ request }) => {
        confirmations.push(await request.json());
        return HttpResponse.json({ status: 'succeeded', membership: CURRENT_MEMBERSHIP });
      }),
    );

    renderWithProviders(<Checkout mode="join" onSuccess={onSuccess} />);
    await user.click(await screen.findByRole('button', { name: 'Pay $45.00' }));

    await waitFor(() =>
      expect(onSuccess).toHaveBeenCalledWith({ paymentId: 77, membership: CURRENT_MEMBERSHIP }),
    );
    expect(confirmations).toEqual([{ payment_id: 77, payment_intent_id: 'pi_1' }]);

    const options = confirmPayment.mock.calls[0]?.[0] as {
      redirect: string;
      confirmParams: { return_url: string };
    };
    expect(options.redirect).toBe('if_required');
    expect(options.confirmParams.return_url).toContain('/portal/join/done?payment_id=77');
  });

  it('shows the card error Stripe reports', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    serveConfig(stripeConfig);
    serveCheckout({ client_secret: 'pi_1_secret_abc' });
    confirmPayment.mockResolvedValue({ error: { message: 'Your card was declined.' } });

    renderWithProviders(<Checkout mode="join" onSuccess={onSuccess} />);
    await user.click(await screen.findByRole('button', { name: 'Pay $45.00' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Your card was declined.');
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it('reports a checkout that could not be started', async () => {
    serveConfig(stripeConfig);
    server.use(
      http.post(`${API}/payments/checkout`, () =>
        HttpResponse.json({ detail: 'Stripe is not configured.' }, { status: 400 }),
      ),
    );

    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Stripe is not configured.');
  });
});

describe('Checkout · PayPal', () => {
  const payPalConfig = config({ providers: ['paypal', 'mock'], paypal_client_id: 'paypal-id' });

  it('creates an order then captures it', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    serveConfig(payPalConfig);
    const requests = serveCheckout({ order_id: 'ORDER-9' });

    const captures: unknown[] = [];
    server.use(
      http.post(`${API}/payments/paypal/capture`, async ({ request }) => {
        captures.push(await request.json());
        return HttpResponse.json({ status: 'succeeded', membership: CURRENT_MEMBERSHIP });
      }),
    );

    renderWithProviders(<Checkout mode="join" onSuccess={onSuccess} />);
    await user.click(await screen.findByRole('button', { name: 'Pay with PayPal' }));

    await waitFor(() =>
      expect(onSuccess).toHaveBeenCalledWith({ paymentId: 77, membership: CURRENT_MEMBERSHIP }),
    );
    expect(requests[0]?.provider).toBe('paypal');
    expect(captures).toEqual([{ payment_id: 77, order_id: 'ORDER-9' }]);
  });

  it('reports a capture that does not complete', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    serveConfig(payPalConfig);
    serveCheckout({ order_id: 'ORDER-9' });
    server.use(
      http.post(`${API}/payments/paypal/capture`, () =>
        HttpResponse.json({ status: 'pending', membership: NO_MEMBERSHIP }),
      ),
    );

    renderWithProviders(<Checkout mode="join" onSuccess={onSuccess} />);
    await user.click(await screen.findByRole('button', { name: 'Pay with PayPal' }));

    const panel = await screen.findByRole('tabpanel');
    expect(await within(panel).findByRole('alert')).toHaveTextContent('did not complete');
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it('shows the reason the server gave for refusing the order', async () => {
    const user = userEvent.setup();
    serveConfig(payPalConfig);
    server.use(
      http.post(`${API}/payments/checkout`, () =>
        HttpResponse.json({ detail: 'That plan is closed to new members.' }, { status: 400 }),
      ),
    );

    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);
    await user.click(await screen.findByRole('button', { name: 'Pay with PayPal' }));

    const panel = await screen.findByRole('tabpanel');
    expect(await within(panel).findByRole('alert')).toHaveTextContent(
      'That plan is closed to new members.',
    );
  });

  it('falls back to its own wording when the failure carries no server message', async () => {
    const user = userEvent.setup();
    serveConfig(payPalConfig);
    // A checkout that comes back without an order id is not an `ApiError`.
    serveCheckout();

    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);
    await user.click(await screen.findByRole('button', { name: 'Pay with PayPal' }));

    const panel = await screen.findByRole('tabpanel');
    expect(await within(panel).findByRole('alert')).toHaveTextContent(
      'That PayPal payment could not be started.',
    );
  });

  it('reports an SDK failure that no checkout call caused', async () => {
    const user = userEvent.setup();
    serveConfig(payPalConfig);
    serveCheckout({ order_id: 'ORDER-9' });

    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);
    await user.click(await screen.findByRole('button', { name: 'Break the PayPal window' }));

    const panel = await screen.findByRole('tabpanel');
    expect(await within(panel).findByRole('alert')).toHaveTextContent(
      'PayPal could not be reached. Please try again.',
    );
  });

  it('says the payment was canceled when the PayPal window is closed', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    serveConfig(payPalConfig);
    serveCheckout({ order_id: 'ORDER-9' });

    renderWithProviders(<Checkout mode="join" onSuccess={onSuccess} />);
    await user.click(await screen.findByRole('button', { name: 'Close the PayPal window' }));

    expect(await screen.findByText('Payment canceled')).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it('leaves the checkout in place after a cancellation', async () => {
    const user = userEvent.setup();
    serveConfig(payPalConfig);
    serveCheckout({ order_id: 'ORDER-9' });

    renderWithProviders(<Checkout mode="join" onSuccess={vi.fn()} />);
    await user.click(await screen.findByRole('button', { name: 'Close the PayPal window' }));

    expect(await screen.findByText('Payment canceled')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pay with PayPal' })).toBeInTheDocument();
    expect(screen.getByTestId('checkout-total')).toHaveTextContent('$45.00');
  });
});

/**
 * A client that keeps a cached query alive without an observer, so the state of
 * a query nothing is watching can still be read after the payment.
 */
function makeRetainingQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: Infinity },
      mutations: { retry: false },
    },
  });
}

describe('Checkout · what a payment refreshes', () => {
  it('leaves every cached query to the flow that hosts it', async () => {
    const user = userEvent.setup();
    const onSuccess = vi.fn();
    serveConfig(config());
    serveCheckout();
    server.use(
      http.post(`${API}/payments/mock/complete`, () =>
        HttpResponse.json({ status: 'succeeded', membership: CURRENT_MEMBERSHIP }),
      ),
    );

    const { client } = renderWithProviders(<Checkout mode="join" onSuccess={onSuccess} />, {
      client: makeRetainingQueryClient(),
    });
    client.setQueryData(AUTH_ME_KEY, makeUser());

    await user.click(await screen.findByRole('button', { name: 'Succeed' }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));

    expect(client.getQueryState(AUTH_ME_KEY)?.isInvalidated).toBe(false);
  });
});
