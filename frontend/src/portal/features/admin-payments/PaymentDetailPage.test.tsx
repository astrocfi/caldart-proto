import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import type { PaymentDetail } from '@/portal/api/types';
import { makeDetail, makeRefund } from '@test/fixtures/finance';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { PaymentDetailPage } from './PaymentDetailPage';

/** Serve one payment, recording the bodies of every write against it. */
function servePayment(payment: PaymentDetail = makeDetail()): Record<string, unknown>[] {
  const bodies: Record<string, unknown>[] = [];
  server.use(
    http.get(`${API}/admin/payments/${payment.id}`, () => HttpResponse.json(payment)),
    http.patch(`${API}/admin/payments/${payment.id}`, async ({ request }) => {
      bodies.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json(payment);
    }),
    http.post(`${API}/admin/payments/${payment.id}/refunds`, async ({ request }) => {
      bodies.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json(
        {
          refund: makeRefund({ amount_cents: 12_000 }),
          payment: {
            id: payment.id,
            amount_cents: payment.amount_cents,
            refunded_cents: 12_000,
            status: 'partially_refunded',
          },
        },
        { status: 201 },
      );
    }),
    http.post(`${API}/admin/payments/${payment.id}/receipt`, () =>
      HttpResponse.json({ sent: true, receipt_sent_at: '2026-03-01T10:00:00Z' }),
    ),
    http.post(`${API}/admin/payments/${payment.id}/fees`, () =>
      HttpResponse.json({ ...payment, fee_cents: 450, net_cents: 14_050 }),
    ),
  );
  return bodies;
}

/** Render the detail screen at the route that gives it its id. */
function renderDetail() {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/payments/:id" element={<PaymentDetailPage />} />
    </Routes>,
    { route: '/admin/payments/412' },
  );
}

describe('PaymentDetailPage', () => {
  it('names the payment by its receipt number', async () => {
    servePayment();
    renderDetail();

    expect(
      await screen.findByRole('heading', { name: 'Payment CALDART-000412' }),
    ).toBeInTheDocument();
  });

  it('shows the term the payment bought', async () => {
    servePayment();
    renderDetail();

    expect(await screen.findByText(/2026\/01\/09/)).toBeInTheDocument();
  });

  it('lists the refunds against the payment', async () => {
    servePayment(makeDetail({ refunds: [makeRefund()] }));
    renderDetail();

    const table = await screen.findByRole('table');
    expect(within(table).getByText('The member asked for it')).toBeInTheDocument();
  });

  it('says when a refund came from the provider dashboard', async () => {
    servePayment(makeDetail({ refunds: [makeRefund({ requested_by_id: null })] }));
    renderDetail();

    const table = await screen.findByRole('table');
    expect(within(table).getByText("The provider's dashboard")).toBeInTheDocument();
  });

  it('says so when nothing has been refunded', async () => {
    servePayment();
    renderDetail();

    expect(await screen.findByText('Nothing has been refunded')).toBeInTheDocument();
  });

  it('offers the whole unrefunded balance in the refund form', async () => {
    const user = userEvent.setup();
    servePayment(makeDetail({ refunded_cents: 2_500 }));
    renderDetail();

    await user.click(await screen.findByRole('button', { name: 'Refund' }));

    expect(screen.getByLabelText(/Amount/)).toHaveValue(120);
  });

  it('sends the refund the form was filled in with', async () => {
    const user = userEvent.setup();
    const bodies = servePayment();
    renderDetail();

    await user.click(await screen.findByRole('button', { name: 'Refund' }));
    await user.selectOptions(screen.getByLabelText(/Reason/), 'duplicate');
    const form = screen.getByRole('form', { name: 'Refund this payment' });
    await user.click(within(form).getByRole('button', { name: 'Refund' }));

    await waitFor(() => expect(bodies[0]).toMatchObject({ reason: 'duplicate' }));
  });

  it('marks the term for cancellation when the refund covers the dues', async () => {
    const user = userEvent.setup();
    servePayment();
    renderDetail();

    await user.click(await screen.findByRole('button', { name: 'Refund' }));

    expect(screen.getByRole('checkbox', { name: /Cancel the membership term/ })).toBeChecked();
  });

  it('leaves the term alone when only part of the dues comes back', async () => {
    const user = userEvent.setup();
    servePayment();
    renderDetail();

    await user.click(await screen.findByRole('button', { name: 'Refund' }));
    await user.clear(screen.getByLabelText(/Amount/));
    await user.type(screen.getByLabelText(/Amount/), '10');

    expect(screen.getByRole('checkbox', { name: /Cancel the membership term/ })).not.toBeChecked();
  });

  it("leaves the treasurer's own answer about the term alone as the amount changes", async () => {
    const user = userEvent.setup();
    servePayment();
    renderDetail();

    await user.click(await screen.findByRole('button', { name: 'Refund' }));
    const box = screen.getByRole('checkbox', { name: /Cancel the membership term/ });
    await user.click(box);
    await user.clear(screen.getByLabelText(/Amount/));
    await user.type(screen.getByLabelText(/Amount/), '145');

    expect(box).not.toBeChecked();
  });

  it('shows a refund error that carries only a sentence', async () => {
    const user = userEvent.setup();
    const payment = makeDetail();
    servePayment(payment);
    server.use(
      http.post(`${API}/admin/payments/${payment.id}/refunds`, () =>
        HttpResponse.json({ detail: 'That payment is no longer refundable.' }, { status: 409 }),
      ),
    );
    renderDetail();

    await user.click(await screen.findByRole('button', { name: 'Refund' }));
    const form = screen.getByRole('form', { name: 'Refund this payment' });
    await user.click(within(form).getByRole('button', { name: 'Refund' }));

    expect(await screen.findByText('That payment is no longer refundable.')).toBeInTheDocument();
  });

  it('writes the reconciliation date the treasurer typed', async () => {
    const user = userEvent.setup();
    const bodies = servePayment();
    renderDetail();

    await user.type(await screen.findByLabelText(/Matched on/), '2026-02-02');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(bodies[0]).toMatchObject({ reconciled_on: '2026-02-02' }));
  });

  it('clears the reconciliation with an empty date', async () => {
    const user = userEvent.setup();
    const bodies = servePayment(makeDetail({ reconciled_on: '2026-02-02' }));
    renderDetail();

    await user.clear(await screen.findByLabelText(/Matched on/));
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(bodies[0]).toMatchObject({ reconciled_on: null }));
  });

  it('offers the fee refresh only while the fee is unknown', async () => {
    servePayment(makeDetail({ fee_cents: 0, net_cents: 0 }));
    renderDetail();

    expect(
      await screen.findByRole('button', { name: 'Fetch fee from provider' }),
    ).toBeInTheDocument();
  });

  it('hides the fee refresh once the provider has reported', async () => {
    servePayment();
    renderDetail();

    await screen.findByRole('heading', { name: 'Payment CALDART-000412' });
    expect(screen.queryByRole('button', { name: 'Fetch fee from provider' })).toBeNull();
  });

  it('says the fee is unreported rather than showing it as zero', async () => {
    servePayment(makeDetail({ fee_cents: 0, net_cents: 0 }));
    renderDetail();

    expect(await screen.findByText('Not reported yet')).toBeInTheDocument();
  });

  it('confirms when the receipt has gone out again', async () => {
    const user = userEvent.setup();
    servePayment();
    renderDetail();

    await user.click(await screen.findByRole('button', { name: 'Resend receipt' }));

    expect(await screen.findByText('Receipt emailed again.')).toBeInTheDocument();
  });

  it('offers the receipt as a download', async () => {
    servePayment();
    renderDetail();

    expect(await screen.findByRole('link', { name: 'Download receipt' })).toHaveAttribute(
      'href',
      '/api/v1/admin/payments/412/receipt.pdf',
    );
  });

  it('links on to the member ledger', async () => {
    servePayment();
    renderDetail();

    expect(
      await screen.findByRole('link', { name: 'Everything Marta Reyes has paid' }),
    ).toHaveAttribute('href', '/admin/payments/members/37');
  });
});
