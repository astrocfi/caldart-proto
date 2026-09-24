/**
 * The Stripe setup panel's traffic to our own server.
 *
 * Every SetupIntent is a real object at Stripe and rewrites the member's
 * pending authority, so the panel must ask for one once the amount has settled
 * rather than once per keystroke.  The clock is faked so the debounce can be
 * settled deliberately.
 */
import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { RenewalSetupRequest } from '@/portal/api/types';
import { AMOUNT_DEBOUNCE_MS } from '@/portal/features/checkout/StripePanel';
import { makePaymentsConfig } from '@test/fixtures/payments';
import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { RenewalSetup } from './RenewalSetup';

vi.mock('@stripe/stripe-js', () => ({
  loadStripe: () => Promise.resolve({ id: 'stripe-stub' }),
}));

vi.mock('@stripe/react-stripe-js', () => ({
  Elements: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PaymentElement: () => <div data-testid="payment-element">Payment element</div>,
  useStripe: () => ({ confirmSetup: vi.fn() }),
  useElements: () => ({}),
}));

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  vi.useRealTimers();
});

/** Serve the config and record every setup request the panel sends. */
function mount() {
  const setups: RenewalSetupRequest[] = [];
  server.use(
    signedInAs(makeUser()),
    http.get(`${API}/payments/config`, () =>
      HttpResponse.json(makePaymentsConfig({ providers: ['stripe'] })),
    ),
    http.post(`${API}/me/renewal/setup`, async ({ request }) => {
      setups.push((await request.json()) as RenewalSetupRequest);
      return HttpResponse.json({ provider: 'stripe', client: { client_secret: 'seti_secret' } });
    }),
  );
  const handleCancel = vi.fn();
  const handleDone = vi.fn();
  renderWithProviders(<RenewalSetup onCancel={handleCancel} onDone={handleDone} />, {
    route: '/payments',
  });
  return { setups };
}

describe('StripeRenewalPanel', () => {
  it('asks for one SetupIntent for an amount typed digit by digit', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const { setups } = mount();

    await user.click(await screen.findByRole('radio', { name: 'Other amount' }));
    await user.type(screen.getByLabelText('Contribution amount'), '250');
    await act(() => vi.advanceTimersByTimeAsync(AMOUNT_DEBOUNCE_MS));

    await waitFor(() =>
      expect(setups).toEqual([
        { plan: 'annual', contribution_cents: 0, provider: 'stripe' },
        { plan: 'annual', contribution_cents: 25000, provider: 'stripe' },
      ]),
    );
  });
});
