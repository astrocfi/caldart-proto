import { screen } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { makeLedger } from '@test/fixtures/finance';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
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
  beforeEach(() => {
    server.use(http.get(`${API}/admin/payments/ledger/1`, () => HttpResponse.json(makeLedger())));
  });

  it('leads with the account actions above the delete', () => {
    renderZone([]);

    expect(screen.getAllByRole('heading').map((heading) => heading.textContent)).toEqual([
      'Account',
      'Delete this member',
    ]);
  });

  it('says where the one payment of a member goes', () => {
    renderZone([PAYMENT]);

    expect(
      screen.getByText(
        'Ana Bracco has 1 payment record. It stays in the books under the name Deleted member 1.',
      ),
    ).toBeInTheDocument();
  });

  it('counts every payment that stays in the books', () => {
    renderZone([PAYMENT, { ...PAYMENT, id: 22, provider_ref: 'pi_456' }]);

    expect(
      screen.getByText(
        'Ana Bracco has 2 payment records. They stay in the books under the name Deleted member 1.',
      ),
    ).toBeInTheDocument();
  });

  it('offers the delete form to a member with payments', () => {
    renderZone([PAYMENT]);

    expect(screen.getByRole('button', { name: 'Delete member' })).toBeDisabled();
  });

  it('asks for the email address of a member with payments', () => {
    renderZone([PAYMENT]);

    expect(screen.getByLabelText(/Type ana@example.org to confirm/)).toBeInTheDocument();
  });

  it('says nothing about payments to a member who never paid', () => {
    renderZone([]);

    expect(screen.queryByText(/stays? in the books/)).not.toBeInTheDocument();
  });

  it('offers the delete form to a member with no payments', () => {
    renderZone([]);

    expect(screen.getByRole('button', { name: 'Delete member' })).toBeDisabled();
  });

  it('leads the delete with the trashcan the rest of the portal uses', () => {
    renderZone([]);

    expect(
      screen.getByRole('button', { name: 'Delete member' }).querySelector('svg'),
    ).toBeInTheDocument();
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
