import { screen, waitFor } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { API, CURRENT_MEMBERSHIP, NO_MEMBERSHIP } from '../../../test/handlers';
import { renderWithProviders } from '../../../test/render';
import { server } from '../../../test/server';
import { CheckoutReturn } from './CheckoutReturn';

const RETURN_URL = '/join/done?payment_id=42&payment_intent=pi_42';

function serveConfirm(status: number, body: Record<string, unknown>) {
  const calls = { count: 0 };
  server.use(
    http.post(`${API}/payments/stripe/confirm`, () => {
      calls.count += 1;
      return HttpResponse.json(body, { status });
    }),
  );
  return calls;
}

/** Answer `GET /payments/42` with each entry in turn, repeating the last. */
function servePayment(sequence: Record<string, unknown>[]) {
  let call = 0;
  const calls = { count: 0 };
  server.use(
    http.get(`${API}/payments/42`, () => {
      const body = sequence[Math.min(call, sequence.length - 1)];
      call += 1;
      calls.count = call;
      return HttpResponse.json(body);
    }),
  );
  return calls;
}

describe('CheckoutReturn', () => {
  it('confirms and hands the membership back straight away', async () => {
    const onSuccess = vi.fn();
    serveConfirm(200, { status: 'succeeded', membership: CURRENT_MEMBERSHIP });

    renderWithProviders(<CheckoutReturn onSuccess={onSuccess} />, { route: RETURN_URL });

    expect(screen.getByRole('status')).toHaveTextContent('Confirming your payment');
    await waitFor(() =>
      expect(onSuccess).toHaveBeenCalledWith({ paymentId: 42, membership: CURRENT_MEMBERSHIP }),
    );
  });

  it('polls the payment when confirmation has not settled yet', async () => {
    const onSuccess = vi.fn();
    serveConfirm(200, { status: 'pending', membership: NO_MEMBERSHIP });
    const calls = servePayment([
      { status: 'pending', membership: NO_MEMBERSHIP },
      { status: 'succeeded', membership: CURRENT_MEMBERSHIP },
    ]);

    renderWithProviders(<CheckoutReturn onSuccess={onSuccess} />, { route: RETURN_URL });

    await waitFor(
      () =>
        expect(onSuccess).toHaveBeenCalledWith({ paymentId: 42, membership: CURRENT_MEMBERSHIP }),
      { timeout: 5_000 },
    );
    expect(calls.count).toBeGreaterThan(1);
  });

  it('polls after a confirm that errors, because the webhook may have won', async () => {
    const onSuccess = vi.fn();
    serveConfirm(400, { detail: 'That PaymentIntent belongs to another payment.' });
    servePayment([{ status: 'succeeded', membership: CURRENT_MEMBERSHIP }]);

    renderWithProviders(<CheckoutReturn onSuccess={onSuccess} />, { route: RETURN_URL });

    await waitFor(() => expect(onSuccess).toHaveBeenCalled(), { timeout: 5_000 });
  });

  it('reports a declined payment', async () => {
    const onSuccess = vi.fn();
    serveConfirm(200, { status: 'pending', membership: NO_MEMBERSHIP });
    servePayment([{ status: 'failed', membership: NO_MEMBERSHIP }]);

    renderWithProviders(<CheckoutReturn onSuccess={onSuccess} />, { route: RETURN_URL });

    expect(await screen.findByText('Payment not confirmed')).toBeInTheDocument();
    expect(screen.getByText(/declined/)).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it('confirms once when StrictMode runs the effect twice', async () => {
    const onSuccess = vi.fn();
    const confirmations = serveConfirm(200, {
      status: 'succeeded',
      membership: CURRENT_MEMBERSHIP,
    });

    renderWithProviders(<CheckoutReturn onSuccess={onSuccess} />, { route: RETURN_URL });

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    expect(confirmations.count).toBe(1);
  });

  it('complains about a link with no payment reference', async () => {
    renderWithProviders(<CheckoutReturn onSuccess={vi.fn()} />, { route: '/join/done' });
    expect(await screen.findByText('Payment not confirmed')).toBeInTheDocument();
    expect(screen.getByText(/missing a payment reference/)).toBeInTheDocument();
  });
});
