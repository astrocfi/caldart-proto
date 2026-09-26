/**
 * `/payments` — the history table, the receipt links and the statement buttons.
 *
 * The renewal card has its own suite; here it is only served enough to render.
 */
import { screen, within } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import type { RequestHandler } from 'msw';
import { describe, expect, it } from 'vitest';

import type { MembershipStatus, PaymentSummary } from '@/portal/api/types';
import { makeMandate, makePaymentSummary, makePaymentsConfig } from '@test/fixtures/payments';
import { API, CURRENT_MEMBERSHIP, LIFETIME_MEMBERSHIP, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { PaymentsPage } from './PaymentsPage';

function mount({
  payments = [],
  years = [],
  extra = [],
  membership = CURRENT_MEMBERSHIP,
}: {
  payments?: PaymentSummary[];
  years?: number[];
  /** Handlers that take precedence over the ones below, for the failure cases. */
  extra?: RequestHandler[];
  membership?: MembershipStatus;
} = {}) {
  server.use(
    ...extra,
    signedInAs(makeUser({ membership })),
    http.get(`${API}/payments/config`, () => HttpResponse.json(makePaymentsConfig())),
    http.get(`${API}/me/membership`, () => HttpResponse.json({ ...membership, history: [] })),
    http.get(`${API}/me/payments`, () => HttpResponse.json(payments)),
    http.get(`${API}/me/payments/statements`, () => HttpResponse.json({ years })),
  );
  return renderWithProviders(<PaymentsPage />, { route: '/payments' });
}

/** The lede once the membership is known to have nothing to renew. */
const NO_RENEWAL_LEDE = 'Your recurring donation, your receipts, and your contribution statements.';

/** Queries scoped to one `<Card>`, found by its heading. */
function card(heading: string) {
  const section = screen.getByRole('heading', { name: heading }).closest('section');
  if (!section) throw new Error(`No card titled "${heading}"`);
  return within(section);
}

describe('PaymentsPage', () => {
  it('tells a member with a dated term the lede is about renewal', async () => {
    mount();

    expect(
      await screen.findByText(
        'Your recurring donation, whether CalDART renews your membership for you, your receipts, and your contribution statements.',
      ),
    ).toBeInTheDocument();
  });

  it('shows a member with a dated term both authorities', async () => {
    mount();

    expect(await screen.findByRole('heading', { name: 'Automatic renewal' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Recurring donation' })).toBeInTheDocument();
  });

  it('tells a life member the lede is about their donation, not a renewal', async () => {
    mount({ membership: LIFETIME_MEMBERSHIP });

    expect(
      await screen.findByText(
        'Your recurring donation, your receipts, and your contribution statements.',
      ),
    ).toBeInTheDocument();
  });

  it('offers a life member no automatic renewal, since nothing of theirs renews', async () => {
    mount({ membership: LIFETIME_MEMBERSHIP });

    expect(await screen.findByText(NO_RENEWAL_LEDE)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Automatic renewal' })).not.toBeInTheDocument();
  });

  it('offers a friend no automatic renewal, since a friend pays no dues', async () => {
    mount({
      membership: { ...CURRENT_MEMBERSHIP, status: 'friend', plan: null, expires_on: null },
    });

    expect(await screen.findByText(NO_RENEWAL_LEDE)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Automatic renewal' })).not.toBeInTheDocument();
  });

  it('shows a life member a renewal they still hold, so they can turn it off', async () => {
    mount({
      membership: LIFETIME_MEMBERSHIP,
      extra: [http.get(`${API}/me/renewal`, () => HttpResponse.json({ mandate: makeMandate() }))],
    });

    expect(await screen.findByRole('heading', { name: 'Automatic renewal' })).toBeInTheDocument();
  });

  it('hides a canceled renewal from a friend', async () => {
    mount({
      membership: { ...CURRENT_MEMBERSHIP, status: 'friend', plan: null, expires_on: null },
      extra: [
        http.get(`${API}/me/renewal`, () =>
          HttpResponse.json({ mandate: makeMandate({ status: 'canceled' }) }),
        ),
      ],
    });

    expect(await screen.findByText(NO_RENEWAL_LEDE)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Automatic renewal' })).not.toBeInTheDocument();
  });

  it('keeps the renewal card when the membership could not be read', async () => {
    mount({
      extra: [http.get(`${API}/me/membership`, () => new HttpResponse(null, { status: 500 }))],
    });

    expect(await screen.findByRole('heading', { name: 'Automatic renewal' })).toBeInTheDocument();
  });

  it('lists a payment with what it bought and a link to its receipt', async () => {
    mount({ payments: [makePaymentSummary({ id: 414, plan: 'Annual', kind: 'both' })] });

    const row = within(await screen.findByRole('row', { name: /Annual and contribution/ }));
    expect(row.getByText('2026/03/14')).toBeInTheDocument();
    expect(row.getByText('$45.00')).toBeInTheDocument();
    expect(row.getByRole('link', { name: 'Receipt' })).toHaveAttribute(
      'href',
      '/api/v1/me/payments/414/receipt.pdf',
    );
  });

  it('names a payment that bought nothing but a contribution', async () => {
    mount({ payments: [makePaymentSummary({ plan: null, kind: 'contribution' })] });

    expect(await screen.findByRole('cell', { name: 'Contribution' })).toBeInTheDocument();
  });

  it('offers no receipt for a payment whose money never arrived', async () => {
    mount({
      payments: [makePaymentSummary({ status: 'failed', paid_on: null, receipt_sent_at: null })],
    });

    await screen.findByRole('table');
    expect(screen.queryByRole('link', { name: 'Receipt' })).not.toBeInTheDocument();
  });

  it('shows the refunded column only when something has come back', async () => {
    mount({ payments: [makePaymentSummary({ refunded_cents: 0 })] });

    await screen.findByRole('table');
    expect(screen.queryByRole('columnheader', { name: 'Refunded' })).not.toBeInTheDocument();
  });

  it('shows what was refunded when part of a payment came back', async () => {
    mount({
      payments: [makePaymentSummary({ status: 'partially_refunded', refunded_cents: 2500 })],
    });

    expect(await screen.findByRole('columnheader', { name: 'Refunded' })).toBeInTheDocument();
    expect(screen.getByText('$25.00')).toBeInTheDocument();
  });

  it('says so plainly when the member has paid nothing yet', async () => {
    mount();

    expect(await screen.findByText('No payments yet')).toBeInTheDocument();
  });

  it('offers one statement button per year the member contributed in', async () => {
    mount({ years: [2026, 2025] });

    const statements = card('Contribution statements');
    expect(await statements.findByRole('link', { name: '2026 statement' })).toHaveAttribute(
      'href',
      '/api/v1/me/payments/statements/2026.pdf',
    );
    expect(statements.getByRole('link', { name: '2025 statement' })).toBeInTheDocument();
  });

  it('explains why a year of dues alone has no statement', async () => {
    mount();

    expect(await screen.findByText('No statements yet')).toBeInTheDocument();
  });

  it('does not pass a failed statements read off as a year with nothing in it', async () => {
    mount({
      extra: [
        http.get(`${API}/me/payments/statements`, () =>
          HttpResponse.json({ detail: 'Server error.' }, { status: 500 }),
        ),
      ],
    });

    expect(await screen.findByText('Your statements could not be loaded')).toBeInTheDocument();
    expect(screen.queryByText('No statements yet')).not.toBeInTheDocument();
  });
});
