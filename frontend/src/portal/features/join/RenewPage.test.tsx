import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import type { CheckoutProps } from '@/portal/features/checkout';

import { API, makeUser, signedInAs } from '../../../test/handlers';
import { renderWithProviders } from '../../../test/render';
import { server } from '../../../test/server';
import type { MembershipDetail } from '../../api/types';
import { RenewPage } from './RenewPage';

const modes: string[] = [];

/** `feat/payments` owns the real checkout; stand in for it to drive success. */
vi.mock('@/portal/features/checkout', () => ({
  Checkout: (props: CheckoutProps) => {
    modes.push(props.mode);
    return (
      <button
        type="button"
        onClick={() =>
          props.onSuccess({
            paymentId: 1,
            membership: {
              status: 'current',
              expires_on: '2028-06-30',
              plan: 'Annual',
              is_lifetime: false,
            },
          })
        }
      >
        Pretend to pay
      </button>
    );
  },
}));

function detail(overrides: Partial<MembershipDetail> = {}): MembershipDetail {
  return {
    status: 'current',
    expires_on: '2027-06-30',
    plan: 'Annual',
    is_lifetime: false,
    history: [],
    ...overrides,
  };
}

function Path() {
  return <span data-testid="path">{useLocation().pathname}</span>;
}

function renderRenew(membership: MembershipDetail) {
  server.use(
    signedInAs(makeUser()),
    http.get(`${API}/me/membership`, () => HttpResponse.json(membership)),
  );
  return renderWithProviders(
    <>
      <Path />
      <Routes>
        <Route path="/renew" element={<RenewPage />} />
        <Route path="/" element={<p>Dashboard</p>} />
      </Routes>
    </>,
    { route: '/renew' },
  );
}

describe('<RenewPage/>', () => {
  it('shows the current status and expiry before the checkout', async () => {
    renderRenew(detail());

    expect(await screen.findByText('Current')).toHaveAttribute('data-tone', 'current');
    expect(screen.getByText(/Jun 30, 2027/)).toBeInTheDocument();
    expect(screen.getByText('Annual membership')).toBeInTheDocument();
  });

  it('says so when the membership has already lapsed', async () => {
    renderRenew(detail({ status: 'expired', expires_on: '2024-06-30' }));

    const chip = await screen.findByText('Expired', { selector: 'span.chip' });
    expect(chip).toHaveAttribute('data-tone', 'expired');
    expect(screen.getByText(/Jun 30, 2024/)).toBeInTheDocument();
  });

  it('tells a life member there is nothing to renew', async () => {
    renderRenew(detail({ expires_on: null, plan: 'Life', is_lifetime: true }));

    expect(
      await screen.findByText('You are a life member — there is nothing to renew.'),
    ).toBeInTheDocument();
  });

  it('renders the checkout in renew mode', async () => {
    renderRenew(detail());

    await screen.findByRole('button', { name: 'Pretend to pay' });
    expect(modes).toContain('renew');
  });

  it('thanks the member and returns to the dashboard on success', async () => {
    renderRenew(detail());

    await userEvent.click(await screen.findByRole('button', { name: 'Pretend to pay' }));

    expect(await screen.findByText('Thank you — your membership is renewed.')).toBeInTheDocument();
    expect(screen.getByTestId('path')).toHaveTextContent('/');
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });
});
