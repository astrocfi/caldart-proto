import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@test/render';
import { MemberDangerZone } from './MemberDangerZone';
import { makeDetail } from '@test/fixtures/members';
import type { MemberPayment } from '@/portal/api/types';

const PAYMENT: MemberPayment = {
  id: 21,
  plan: 'Annual',
  amount_cents: 6500,
  plan_amount_cents: 4500,
  contribution_cents: 2000,
  currency: 'usd',
  provider: 'stripe',
  wallet: 'card',
  provider_ref: 'pi_123',
  status: 'succeeded',
  created_at: '2026-07-01T12:00:00Z',
  completed_at: '2026-07-01T12:00:05Z',
};

function renderZone(payments: MemberPayment[]) {
  return renderWithProviders(<MemberDangerZone member={makeDetail({ payments })} />);
}

describe('MemberDangerZone', () => {
  it('says why a member with one payment cannot be deleted', () => {
    renderZone([PAYMENT]);

    expect(
      screen.getByText(
        'Ana Bracco has 1 payment record, which must be kept. Deleting the account would ' +
          'take the payment history with it, so the delete is refused.',
      ),
    ).toBeInTheDocument();
  });

  it('counts every payment in the explanation', () => {
    renderZone([PAYMENT, { ...PAYMENT, id: 22, provider_ref: 'pi_456' }]);

    expect(
      screen.getByText(
        'Ana Bracco has 2 payment records, which must be kept. Deleting the account would ' +
          'take the payment history with it, so the delete is refused.',
      ),
    ).toBeInTheDocument();
  });

  it('points at deactivation instead', () => {
    renderZone([PAYMENT]);

    expect(
      screen.getByText(
        'Clear Account is active on the Profile tab instead. A deactivated member cannot ' +
          'sign in, and their profile, membership terms and payments stay exactly as they are.',
      ),
    ).toBeInTheDocument();
  });

  it('offers no delete form to a member with payments', () => {
    renderZone([PAYMENT]);

    expect(screen.queryByRole('button', { name: 'Delete member' })).not.toBeInTheDocument();
  });

  it('asks no confirmation of a member with payments', () => {
    renderZone([PAYMENT]);

    expect(screen.queryByLabelText(/Type ana@example.org to confirm/)).not.toBeInTheDocument();
  });

  it('offers the delete form to a member with no payments', () => {
    renderZone([]);

    expect(screen.getByRole('button', { name: 'Delete member' })).toBeDisabled();
  });

  it('names the profile and the membership terms the delete takes', () => {
    renderZone([]);

    expect(
      screen.getByText(
        /also deletes their profile and 1 membership term\. This cannot be undone\./,
      ),
    ).toBeInTheDocument();
  });
});
