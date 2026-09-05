import { screen, within } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { API, makeUser, signedInAs } from '../../../test/handlers';
import { renderWithProviders } from '../../../test/render';
import { server } from '../../../test/server';
import type {
  MembershipDetail,
  MembershipStatus,
  PaymentSummary,
  SiteConfig,
  User,
} from '../../api/types';
import { DashboardPage } from './DashboardPage';

const SITE_CONFIG: SiteConfig = {
  org_name: 'CalDART',
  theme: 'sierra',
  contact_email: 'info@example.org',
  nav: [],
  members_pages: [],
};

/** A date far enough out that the dashboard is calm about it. */
function isoIn(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function membership(status: MembershipStatus): MembershipDetail {
  return { ...status, history: [] };
}

function mount({
  user,
  status,
  payments = [],
  config = SITE_CONFIG,
}: {
  user: User;
  status: MembershipStatus;
  payments?: PaymentSummary[];
  config?: SiteConfig;
}) {
  server.use(
    signedInAs(user),
    http.get(`${API}/me/membership`, () => HttpResponse.json(membership(status))),
    http.get(`${API}/me/payments`, () => HttpResponse.json(payments)),
    http.get(`${API}/site/config`, () => HttpResponse.json(config)),
  );
  return renderWithProviders(<DashboardPage />, { route: '/' });
}

/** Queries scoped to one `<Card>`, found by its heading. */
function card(heading: string) {
  const section = screen.getByRole('heading', { name: heading }).closest('section');
  if (!section) throw new Error(`No card titled "${heading}"`);
  return within(section);
}

const CURRENT: MembershipStatus = {
  status: 'current',
  expires_on: isoIn(200),
  plan: 'Annual',
  is_lifetime: false,
};

const EXPIRING: MembershipStatus = { ...CURRENT, expires_on: isoIn(9) };

const EXPIRED: MembershipStatus = {
  status: 'expired',
  expires_on: isoIn(-40),
  plan: 'Annual',
  is_lifetime: false,
};

const NONE: MembershipStatus = {
  status: 'none',
  expires_on: null,
  plan: null,
  is_lifetime: false,
};

const LIFETIME: MembershipStatus = {
  status: 'current',
  expires_on: null,
  plan: 'Life',
  is_lifetime: true,
};

describe('<DashboardPage/>', () => {
  beforeEach(() => {
    server.use(http.get(`${API}/site/config`, () => HttpResponse.json(SITE_CONFIG)));
  });

  it('greets a current member and offers a quiet renewal', async () => {
    mount({ user: makeUser({ membership: CURRENT }), status: CURRENT });

    await screen.findByRole('heading', { name: 'Your membership is current' });
    const status = card('Your membership is current');
    expect(status.getByText('Current')).toHaveAttribute('data-tone', 'current');
    expect(screen.getByRole('heading', { name: 'Welcome, Marta' })).toBeInTheDocument();
    expect(status.getByRole('link', { name: 'Renew' })).toHaveClass('button--secondary');
  });

  it('warns when the membership expires within 30 days', async () => {
    mount({ user: makeUser({ membership: EXPIRING }), status: EXPIRING });

    await screen.findByRole('heading', { name: 'Your membership is current' });
    const status = card('Your membership is current');
    expect(status.getByText('Expiring soon')).toHaveAttribute('data-tone', 'expiring');
    expect(status.getByRole('link', { name: 'Renew' })).not.toHaveClass('button--secondary');
  });

  it('leads with "Renew now" once the membership has expired', async () => {
    mount({ user: makeUser({ membership: EXPIRED }), status: EXPIRED });

    await screen.findByRole('heading', { name: 'Your membership has expired' });
    expect(
      card('Your membership has expired').getByRole('link', { name: 'Renew now' }),
    ).toHaveAttribute('href', '/renew');
  });

  it('sends someone who has never joined to the wizard', async () => {
    mount({ user: makeUser({ membership: NONE }), status: NONE });

    await screen.findByRole('heading', { name: 'You are not a member yet' });
    const status = card('You are not a member yet');
    expect(status.getByRole('link', { name: 'Join CalDART' })).toHaveAttribute('href', '/join');
    expect(status.queryByRole('link', { name: /Renew/ })).not.toBeInTheDocument();
  });

  it('never asks a life member to renew', async () => {
    mount({ user: makeUser({ membership: LIFETIME }), status: LIFETIME });

    await screen.findByRole('heading', { name: 'Lifetime member' });
    const status = card('Lifetime member');
    expect(status.getByText('Nothing to renew — thank you for joining for life.')).toBeVisible();
    expect(status.queryByRole('link', { name: /Renew/ })).not.toBeInTheDocument();
  });

  it('nudges a member whose profile is incomplete', async () => {
    mount({
      user: makeUser({ membership: CURRENT, profile_complete: false }),
      status: CURRENT,
    });

    expect(await screen.findByText('Finish your profile')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Complete my profile' })).toHaveAttribute(
      'href',
      '/profile',
    );
  });

  it('leaves a complete profile alone', async () => {
    mount({ user: makeUser({ membership: CURRENT }), status: CURRENT });

    await screen.findByText('Your membership is current');
    expect(screen.queryByText('Finish your profile')).not.toBeInTheDocument();
  });

  it('filters the quick links by role', async () => {
    mount({
      user: makeUser({ membership: CURRENT, roles: ['member', 'account_admin'] }),
      status: CURRENT,
    });

    // The rail is role-filtered, so wait until `/auth/me` has actually landed.
    await screen.findByRole('heading', { name: 'Welcome, Marta' });
    const links = card('Quick links');
    expect(links.getByRole('link', { name: 'My profile' })).toBeInTheDocument();
    expect(links.getByRole('link', { name: 'Members' })).toBeInTheDocument();
    expect(links.queryByRole('link', { name: 'System' })).not.toBeInTheDocument();
    // The dashboard does not link to itself.
    expect(links.queryByRole('link', { name: 'Dashboard' })).not.toBeInTheDocument();
  });

  it('hides administration links from a plain member', async () => {
    mount({ user: makeUser({ membership: CURRENT }), status: CURRENT });

    // The rail is role-filtered, so wait until `/auth/me` has actually landed.
    await screen.findByRole('heading', { name: 'Welcome, Marta' });
    const links = card('Quick links');
    expect(links.queryByRole('link', { name: 'Members' })).not.toBeInTheDocument();
    expect(links.queryByRole('link', { name: 'Member check' })).not.toBeInTheDocument();
  });

  it('lists the members-only pages the site config offers', async () => {
    mount({
      user: makeUser({ membership: CURRENT }),
      status: CURRENT,
      config: {
        ...SITE_CONFIG,
        members_pages: [{ title: 'Ops manual', url: '/members/ops-manual/' }],
      },
    });

    expect(await screen.findByRole('link', { name: 'Ops manual' })).toHaveAttribute(
      'href',
      '/members/ops-manual/',
    );
  });

  it('has an empty state when nothing members-only is published', async () => {
    mount({ user: makeUser({ membership: CURRENT }), status: CURRENT });

    expect(await screen.findByText('Nothing published yet')).toBeInTheDocument();
  });

  it('shows recent payments newest first, capped at five', async () => {
    const payments: PaymentSummary[] = Array.from({ length: 7 }, (_, index) => ({
      id: 100 - index,
      plan: 'Annual',
      amount_cents: 4500 + index,
      contribution_cents: 0,
      provider: 'stripe',
      status: 'succeeded',
      completed_at: `2026-0${index + 1}-01T12:00:00Z`,
    }));

    mount({ user: makeUser({ membership: CURRENT }), status: CURRENT, payments });

    expect(await screen.findByText('$45.00')).toBeInTheDocument();
    expect(screen.getAllByRole('row')).toHaveLength(6); // header + 5
  });

  it('has an empty state when there are no payments', async () => {
    mount({ user: makeUser({ membership: CURRENT }), status: CURRENT });

    expect(await screen.findByText('No payments yet')).toBeInTheDocument();
  });
});
