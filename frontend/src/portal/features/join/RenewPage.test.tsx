import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import type { CheckoutProps } from '@/portal/features/checkout';

import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { makeMandate } from '@test/fixtures/payments';
import type { MembershipDetail } from '@/portal/api/types';
import { RenewPage } from './RenewPage';

const modes: string[] = [];
const autoRenewDefaults: (boolean | undefined)[] = [];

/** The real checkout is tested on its own; this stand-in records `mode` and drives success. */
vi.mock('@/portal/features/checkout', () => ({
  Checkout: (props: CheckoutProps) => {
    modes.push(props.mode);
    autoRenewDefaults.push(props.defaultAutoRenew);
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
        <Route path="/membership/join" element={<p>Become a member</p>} />
        <Route path="/donate" element={<p>Donate</p>} />
      </Routes>
    </>,
    { route: '/renew' },
  );
}

describe('<RenewPage/>', () => {
  it('shows the current status and expiry before the checkout', async () => {
    renderRenew(detail());

    expect(await screen.findByText('Current')).toHaveAttribute('data-tone', 'current');
    expect(screen.getByText('06/30/2027')).toBeInTheDocument();
    expect(screen.getByText('Annual membership')).toBeInTheDocument();
  });

  it('says so when the membership has already lapsed', async () => {
    renderRenew(detail({ status: 'expired', expires_on: '2024-06-30' }));

    const status = await screen.findByText('Expired', { selector: 'span.status' });
    expect(status).toHaveAttribute('data-tone', 'expired');
    expect(screen.getByText('06/30/2024')).toBeInTheDocument();
  });

  it('sends a life member, who has nothing to renew, to Donate', async () => {
    renderRenew(detail({ expires_on: null, plan: 'Life', is_lifetime: true }));

    expect(await screen.findByText('Donate')).toBeInTheDocument();
    expect(screen.getByTestId('path')).toHaveTextContent('/donate');
  });

  it('does not repeat the page title over the checkout', async () => {
    renderRenew(detail());

    await screen.findByRole('button', { name: 'Pretend to pay' });
    expect(screen.getAllByText('Renew your membership')).toHaveLength(1);
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

  it('sends a friend, who has nothing to renew, to become a member', async () => {
    renderRenew(detail({ status: 'friend', expires_on: null, plan: null }));

    expect(await screen.findByText('Become a member')).toBeInTheDocument();
    expect(screen.getByTestId('path')).toHaveTextContent('/membership/join');
  });

  it('tells a member whose term is current that renewing early costs nothing', async () => {
    renderRenew(detail());

    expect(
      await screen.findByText(/A renewal starts the day after your current term ends/),
    ).toBeInTheDocument();
  });

  it('tells a member whose term has lapsed that the new year starts today', async () => {
    renderRenew(detail({ status: 'expired', expires_on: '2024-06-30' }));

    expect(await screen.findByText('Your new year starts today.')).toBeInTheDocument();
    expect(screen.queryByText(/day after your current term ends/)).not.toBeInTheDocument();
  });
});

describe('<RenewPage/> with automatic renewal on', () => {
  function renderCovered() {
    server.use(
      http.get(`${API}/me/renewal`, () =>
        HttpResponse.json({
          mandate: makeMandate({ amount_cents: 14500, next_charge_on: '2027-04-27' }),
        }),
      ),
    );
    return renderRenew(detail());
  }

  it('says what automatic renewal will charge, and when', async () => {
    renderCovered();

    expect(
      await screen.findByText(
        'We will charge $145.00 on 04/27/2027. You do not need to do anything.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Automatic renewal is on' })).toBeInTheDocument();
  });

  it('holds the checkout back behind Renew now anyway', async () => {
    renderCovered();

    await screen.findByRole('button', { name: 'Renew now anyway' });
    expect(screen.queryByRole('button', { name: 'Pretend to pay' })).not.toBeInTheDocument();
  });

  it('opens the checkout, with the focus in it, on Renew now anyway', async () => {
    renderCovered();

    await userEvent.click(await screen.findByRole('button', { name: 'Renew now anyway' }));

    expect(screen.getByRole('button', { name: 'Pretend to pay' })).toHaveFocus();
  });

  it('keeps saying renewal is on above the open checkout, its box checked', async () => {
    renderCovered();

    await userEvent.click(await screen.findByRole('button', { name: 'Renew now anyway' }));

    expect(screen.getByRole('heading', { name: 'Automatic renewal is on' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Renew now anyway' })).not.toBeInTheDocument();
    expect(autoRenewDefaults.at(-1)).toBe(true);
  });

  it('says a declined charge will be tried again', async () => {
    server.use(
      http.get(`${API}/me/renewal`, () =>
        HttpResponse.json({
          mandate: makeMandate({
            amount_cents: 14500,
            next_charge_on: '2027-04-27',
            failure_count: 1,
          }),
        }),
      ),
    );
    renderRenew(detail());

    expect(
      await screen.findByText(
        'The last charge was declined. CalDART will try again on 04/27/2027, for $145.00.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Renew now anyway' })).toBeInTheDocument();
  });
});

describe('<RenewPage/> with automatic renewal long past its day', () => {
  it('says renewal is paused and offers the checkout at once', async () => {
    server.use(
      http.get(`${API}/me/renewal`, () =>
        HttpResponse.json({
          mandate: makeMandate({ amount_cents: 14500, next_charge_on: '2020-01-15' }),
        }),
      ),
    );
    renderRenew(detail({ status: 'expired', expires_on: '2020-01-16' }));

    expect(
      await screen.findByRole('heading', { name: 'Automatic renewal is paused' }),
    ).toBeInTheDocument();
    expect(screen.getByText(/01\/15\/2020, passed more than 30 days ago/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pretend to pay' })).toBeInTheDocument();
    expect(screen.queryByText(/We will charge/)).not.toBeInTheDocument();
  });
});
