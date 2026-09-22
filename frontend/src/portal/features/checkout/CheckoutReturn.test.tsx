import { act, screen, waitFor } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API, CURRENT_MEMBERSHIP, NO_MEMBERSHIP } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { CheckoutReturn, POLL_INTERVAL_MS, POLL_TIMEOUT_MS } from './CheckoutReturn';

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
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('confirms and hands the membership back straight away', async () => {
    const onSuccess = vi.fn();
    serveConfirm(200, { status: 'succeeded', membership: CURRENT_MEMBERSHIP });

    renderWithProviders(<CheckoutReturn onSuccess={onSuccess} />, { route: RETURN_URL });

    expect(screen.getByRole('status')).toHaveTextContent('Confirming your payment…');
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

    await waitFor(() => expect(calls.count).toBe(1));
    await act(() => vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS));

    expect(onSuccess).toHaveBeenCalledWith({ paymentId: 42, membership: CURRENT_MEMBERSHIP });
    expect(calls.count).toBe(2);
  });

  it('stops asking as soon as the payment succeeds', async () => {
    const onSuccess = vi.fn();
    serveConfirm(200, { status: 'pending', membership: NO_MEMBERSHIP });
    const calls = servePayment([
      { status: 'pending', membership: NO_MEMBERSHIP },
      { status: 'succeeded', membership: CURRENT_MEMBERSHIP },
    ]);

    renderWithProviders(<CheckoutReturn onSuccess={onSuccess} />, { route: RETURN_URL });

    await waitFor(() => expect(calls.count).toBe(1));
    await act(() => vi.advanceTimersByTimeAsync(POLL_INTERVAL_MS * 5));

    expect(calls.count).toBe(2);
    expect(onSuccess).toHaveBeenCalledTimes(1);
  });

  it('gives up and says the payment is still being processed after the timeout', async () => {
    const onSuccess = vi.fn();
    serveConfirm(200, { status: 'pending', membership: NO_MEMBERSHIP });
    servePayment([{ status: 'pending', membership: NO_MEMBERSHIP }]);

    renderWithProviders(<CheckoutReturn onSuccess={onSuccess} />, { route: RETURN_URL });

    await act(() => vi.advanceTimersByTimeAsync(POLL_TIMEOUT_MS + POLL_INTERVAL_MS));

    expect(await screen.findByText('Payment not confirmed')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Your payment is still being processed. It is safe to close this page — we will ' +
          'email you when it clears, and your membership page will update on its own.',
      ),
    ).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it('polls after a confirm that errors, because the webhook may have won', async () => {
    const onSuccess = vi.fn();
    serveConfirm(400, { detail: 'That PaymentIntent belongs to another payment.' });
    servePayment([{ status: 'succeeded', membership: CURRENT_MEMBERSHIP }]);

    renderWithProviders(<CheckoutReturn onSuccess={onSuccess} />, { route: RETURN_URL });

    await waitFor(() =>
      expect(onSuccess).toHaveBeenCalledWith({ paymentId: 42, membership: CURRENT_MEMBERSHIP }),
    );
  });

  it('shows what the server said when the payment lookup is refused', async () => {
    const onSuccess = vi.fn();
    serveConfirm(200, { status: 'pending', membership: NO_MEMBERSHIP });
    server.use(
      http.get(`${API}/payments/42`, () =>
        HttpResponse.json({ detail: 'That payment is not yours.' }, { status: 403 }),
      ),
    );

    renderWithProviders(<CheckoutReturn onSuccess={onSuccess} />, { route: RETURN_URL });

    expect(await screen.findByText('Payment not confirmed')).toBeInTheDocument();
    expect(screen.getByText('That payment is not yours.')).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it('falls back to its own wording when the payment lookup fails outright', async () => {
    const onSuccess = vi.fn();
    serveConfirm(200, { status: 'pending', membership: NO_MEMBERSHIP });
    server.use(http.get(`${API}/payments/42`, () => HttpResponse.error()));

    renderWithProviders(<CheckoutReturn onSuccess={onSuccess} />, { route: RETURN_URL });

    expect(await screen.findByText('Payment not confirmed')).toBeInTheDocument();
    expect(screen.getByText('We could not check that payment.')).toBeInTheDocument();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it('reports a declined payment', async () => {
    const onSuccess = vi.fn();
    serveConfirm(200, { status: 'pending', membership: NO_MEMBERSHIP });
    servePayment([{ status: 'failed', membership: NO_MEMBERSHIP }]);

    renderWithProviders(<CheckoutReturn onSuccess={onSuccess} />, { route: RETURN_URL });

    expect(await screen.findByText('Payment not confirmed')).toBeInTheDocument();
    expect(screen.getByText('That payment was declined. Nothing was charged.')).toBeInTheDocument();
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
    expect(screen.getByText('That link is missing a payment reference.')).toBeInTheDocument();
  });
});
