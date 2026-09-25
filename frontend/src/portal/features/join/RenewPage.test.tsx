import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import type { CheckoutProps } from '@/portal/features/checkout';

import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { MembershipDetail } from '@/portal/api/types';
import { RenewPage } from './RenewPage';

const modes: string[] = [];

/** The real checkout is tested on its own; this stand-in records `mode` and drives success. */
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
    expect(screen.getByText('2027/06/30')).toBeInTheDocument();
    expect(screen.getByText('Annual membership')).toBeInTheDocument();
  });

  it('says so when the membership has already lapsed', async () => {
    renderRenew(detail({ status: 'expired', expires_on: '2024-06-30' }));

    const chip = await screen.findByText('Expired', { selector: 'span.chip' });
    expect(chip).toHaveAttribute('data-tone', 'expired');
    expect(screen.getByText('2024/06/30')).toBeInTheDocument();
  });

  it('thanks a life member rather than offering a renewal', async () => {
    renderRenew(detail({ expires_on: null, plan: 'Life', is_lifetime: true }));

    expect(await screen.findByText('You are a life member. Thank you.')).toBeInTheDocument();
  });

  it('asks a life member to contribute instead', async () => {
    renderRenew(detail({ expires_on: null, plan: 'Life', is_lifetime: true }));

    expect(
      await screen.findByRole('heading', { name: 'Contribute to CalDART', level: 1 }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'As a life member you have nothing to renew. A contribution keeps the DARTs flying.',
      ),
    ).toBeInTheDocument();
  });

  it('runs the checkout in contribute mode for a life member', async () => {
    renderRenew(detail({ expires_on: null, plan: 'Life', is_lifetime: true }));

    // The mode follows the membership, so the first render is whatever the page
    // was asked for and the one that matters is the render after it arrives.
    await waitFor(() => expect(modes.at(-1)).toBe('contribute'));
  });

  it('thanks a life member for the contribution the checkout took', async () => {
    renderRenew(detail({ expires_on: null, plan: 'Life', is_lifetime: true }));

    await userEvent.click(await screen.findByRole('button', { name: 'Pretend to pay' }));

    expect(await screen.findByText('Thank you for your contribution.')).toBeInTheDocument();
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
