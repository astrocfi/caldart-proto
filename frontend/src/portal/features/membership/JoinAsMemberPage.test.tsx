import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import type { CheckoutProps } from '@/portal/features/checkout';

import { makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { JoinAsMemberPage } from './JoinAsMemberPage';

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
              expires_on: '2027-09-25',
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

function Path() {
  return <span data-testid="path">{useLocation().pathname}</span>;
}

function renderPage() {
  server.use(signedInAs(makeUser({ kind: 'friend' })));
  return renderWithProviders(
    <>
      <Path />
      <Routes>
        <Route path="/membership/join" element={<JoinAsMemberPage />} />
        <Route path="/" element={<p>Dashboard</p>} />
      </Routes>
    </>,
    { route: '/membership/join' },
  );
}

describe('<JoinAsMemberPage/>', () => {
  it('is headed Become a member', async () => {
    renderPage();
    expect(
      await screen.findByRole('heading', { name: 'Become a member', level: 1 }),
    ).toBeInTheDocument();
  });

  it('says leaving the page changes nothing', async () => {
    renderPage();
    expect(await screen.findByText(/Nothing changes if you leave this page\./)).toBeInTheDocument();
  });

  it('runs the checkout in join mode', async () => {
    renderPage();
    await screen.findByRole('button', { name: 'Pretend to pay' });
    expect(modes).toContain('join');
  });

  it('welcomes the new member and returns to the dashboard once they have paid', async () => {
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: 'Pretend to pay' }));
    expect(
      await screen.findByText('Thank you — you are a member of CalDART.'),
    ).toBeInTheDocument();
    expect(screen.getByTestId('path')).toHaveTextContent(/^\/$/);
  });
});
