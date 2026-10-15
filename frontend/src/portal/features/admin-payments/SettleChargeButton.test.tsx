import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import type { RenewalAttempt, RenewalSettleResult } from '@/portal/api/types';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { SettleChargeButton } from './SettleChargeButton';

const IN_DOUBT: RenewalAttempt = {
  id: 88,
  mandate_id: 13,
  mandate_kind: 'renewal',
  membership_id: 455,
  payment_id: 901,
  user_id: 35,
  user_name: 'Ben Ortiz',
  scheduled_on: '2026-03-15',
  outcome: 'scheduled',
  error: 'PayPal never answered the renewal order, so it may hold a charge.',
  noticed_at: '2026-03-01T06:30:11Z',
  attempted_at: null,
  in_doubt: true,
  flagged_at: '2026-03-15T06:34:00Z',
  payment_amount_cents: 4500,
  payment_sent_at: '2026-03-15T13:30:00Z',
  result_emailed_at: null,
  created_at: '2026-03-01T06:30:11Z',
};

/** The settle call's answer: the attempt settled, and how to reach Ben. */
const SETTLED: RenewalSettleResult = {
  ...IN_DOUBT,
  in_doubt: false,
  outcome: 'succeeded',
  user_email: 'ben@example.org',
  user_phone: '415-555-0142',
  member_emailed: true,
};

/** Answer the settle call with the attempt settled, keeping each body sent. */
function settling(bodies: unknown[]): void {
  server.use(
    http.post(`${API}/admin/renewals/attempts/88/settle`, async ({ request }) => {
      bodies.push(await request.json());
      return HttpResponse.json(SETTLED);
    }),
  );
}

async function openPanel(handleClosed = vi.fn()): Promise<void> {
  renderWithProviders(<SettleChargeButton attempt={IN_DOUBT} onClosed={handleClosed} />);
  await userEvent.click(screen.getByRole('button', { name: 'Settle the charge for Ben Ortiz' }));
}

/** Confirm the search and press Close as failed. */
async function closeAsFailed(): Promise<void> {
  await userEvent.click(
    screen.getByLabelText('I searched the dashboard and didn’t find a payment for this invoice'),
  );
  await userEvent.click(screen.getByRole('button', { name: 'Close as failed' }));
}

describe('SettleChargeButton', () => {
  it('holds Record as paid back until the provider id is entered', async () => {
    await openPanel();

    expect(screen.getByRole('button', { name: 'Record as paid' })).toBeDisabled();
  });

  it('records the charge as paid with the id entered', async () => {
    const bodies: unknown[] = [];
    settling(bodies);
    await openPanel();

    await userEvent.type(screen.getByLabelText('Capture ID'), ' 8MC585209K746392H ');
    await userEvent.click(screen.getByRole('button', { name: 'Record as paid' }));

    expect(await screen.findByText('The charge for Ben Ortiz is recorded.')).toBeInTheDocument();
    expect(bodies).toEqual([{ outcome: 'paid', reference: '8MC585209K746392H' }]);
  });

  it('names the invoice id to search the dashboard for', async () => {
    await openPanel();

    expect(screen.getByText('caldart-renewal-901')).toBeInTheDocument();
  });

  it('holds No payment found back until the search is confirmed', async () => {
    await openPanel();

    expect(screen.getByRole('button', { name: 'No payment found' })).toBeDisabled();
  });

  it('holds Close as failed back until the search is confirmed', async () => {
    await openPanel();

    expect(screen.getByRole('button', { name: 'Close as failed' })).toBeDisabled();
  });

  it('releases a charge the provider never took', async () => {
    const bodies: unknown[] = [];
    settling(bodies);
    await openPanel();

    await userEvent.click(
      screen.getByLabelText('I searched the dashboard and didn’t find a payment for this invoice'),
    );
    await userEvent.click(screen.getByRole('button', { name: 'No payment found' }));

    expect(
      await screen.findByText('The charge for Ben Ortiz will be taken on the next run.'),
    ).toBeInTheDocument();
    expect(bodies).toEqual([{ outcome: 'released' }]);
  });

  it('closes a charge as failed', async () => {
    const bodies: unknown[] = [];
    settling(bodies);
    await openPanel();

    await closeAsFailed();

    await waitFor(() => expect(bodies).toEqual([{ outcome: 'failed' }]));
  });

  it('hands the answer to a charge closed as failed to the page', async () => {
    settling([]);
    const handleClosed = vi.fn();
    await openPanel(handleClosed);

    await closeAsFailed();

    await waitFor(() => expect(handleClosed).toHaveBeenCalledWith(SETTLED));
  });

  it('says the member is emailed when a charge is closed as failed, and asks for a call', async () => {
    await openPanel();

    expect(
      screen.getByText(/They are emailed that it is paused; please get in touch with them too\./),
    ).toBeInTheDocument();
  });

  it('names a recurring donation in what Close as failed pauses', async () => {
    const handleClosed = vi.fn();
    renderWithProviders(
      <SettleChargeButton
        attempt={{ ...IN_DOUBT, mandate_kind: 'contribution', membership_id: null }}
        onClosed={handleClosed}
      />,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Settle the charge for Ben Ortiz' }));

    expect(screen.getByText(/pauses Ben Ortiz’s recurring donation\./)).toBeInTheDocument();
  });

  it('says why when the provider will not confirm the id', async () => {
    server.use(
      http.post(`${API}/admin/renewals/attempts/88/settle`, () =>
        HttpResponse.json(
          { detail: 'That PayPal capture belongs to another payment.' },
          { status: 400 },
        ),
      ),
    );
    await openPanel();

    await userEvent.type(screen.getByLabelText('Capture ID'), 'CAPTURE-OTHER');
    await userEvent.click(screen.getByRole('button', { name: 'Record as paid' }));

    expect(
      await screen.findByText('That PayPal capture belongs to another payment.'),
    ).toBeInTheDocument();
  });
});
