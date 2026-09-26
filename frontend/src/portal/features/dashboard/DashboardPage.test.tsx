import { screen, within } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { makeContributionMandate, makeMandate } from '@test/fixtures/payments';
import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type {
  MembershipDetail,
  MembershipStatus,
  PaymentSummary,
  SiteConfig,
  User,
} from '@/portal/api/types';
import { EXPIRING_WINDOW_DAYS } from '@/portal/components/StatusChip';
import { DashboardPage } from './DashboardPage';

const NOW = new Date('2026-06-15T12:00:00Z');

const OPS_MANUAL = { title: 'Ops manual', url: '/members/ops-manual/' };

const SITE_CONFIG: SiteConfig = {
  org_name: 'CalDART',
  theme: 'sierra',
  contact_email: 'info@example.org',
  nav: [],
  members_pages: [],
};

/** `NOW` plus `days`, as a local calendar date, the way `daysUntil` reads it. */
function isoIn(days: number): string {
  const date = new Date(NOW);
  date.setDate(date.getDate() + days);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
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
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(NOW);
    server.use(http.get(`${API}/site/config`, () => HttpResponse.json(SITE_CONFIG)));
  });

  afterEach(() => {
    vi.useRealTimers();
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

  it('is still current one day outside the expiring window', async () => {
    const status: MembershipStatus = { ...CURRENT, expires_on: isoIn(EXPIRING_WINDOW_DAYS + 1) };
    mount({ user: makeUser({ membership: status }), status });

    await screen.findByRole('heading', { name: 'Your membership is current' });
    const chip = card('Your membership is current');
    expect(chip.getByText('Current')).toHaveAttribute('data-tone', 'current');
  });

  it('is expiring soon one day inside the expiring window', async () => {
    const status: MembershipStatus = { ...CURRENT, expires_on: isoIn(EXPIRING_WINDOW_DAYS - 1) };
    mount({ user: makeUser({ membership: status }), status });

    await screen.findByRole('heading', { name: 'Your membership is current' });
    const chip = card('Your membership is current');
    expect(chip.getByText('Expiring soon')).toHaveAttribute('data-tone', 'expiring');
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
    expect(status.getByText('Never expires')).toBeVisible();
    expect(status.getByText('Nothing to renew — thank you for joining for life.')).toBeVisible();
    expect(status.queryByRole('link', { name: /Renew/ })).not.toBeInTheDocument();
    // The headline already says it is a life membership; the plan line would
    // be the third time on one card.
    expect(status.queryByText(/membership$/)).not.toBeInTheDocument();
  });

  describe('for a friend', () => {
    const FRIEND: MembershipStatus = { ...NONE, status: 'friend' };

    function mountFriend() {
      return mount({ user: makeUser({ kind: 'friend', membership: FRIEND }), status: FRIEND });
    }

    it('heads the card as a friend of CalDART', async () => {
      mountFriend();

      await screen.findByRole('heading', { name: 'You are a friend of CalDART' });
      expect(card('You are a friend of CalDART').getByText('Friend of CalDART')).toBeVisible();
    });

    it('says what being a friend means', async () => {
      mountFriend();

      await screen.findByRole('heading', { name: 'You are a friend of CalDART' });
      expect(
        card('You are a friend of CalDART').getByText(
          'You are a friend of CalDART: no dues, no expiry. Become a member any time.',
        ),
      ).toBeVisible();
    });

    it('offers membership rather than a renewal or the join wizard', async () => {
      mountFriend();

      await screen.findByRole('heading', { name: 'You are a friend of CalDART' });
      const status = card('You are a friend of CalDART');
      expect(status.getByRole('link', { name: 'Make me a member' })).toHaveAttribute(
        'href',
        '/membership/join',
      );
      expect(status.queryByRole('link', { name: /Renew/ })).not.toBeInTheDocument();
      expect(status.queryByRole('link', { name: 'Join CalDART' })).not.toBeInTheDocument();
    });

    it('gives the card no urgent edge', async () => {
      mountFriend();

      await screen.findByRole('heading', { name: 'You are a friend of CalDART' });
      const section = screen
        .getByRole('heading', { name: 'You are a friend of CalDART' })
        .closest('section');
      expect(section).not.toHaveClass('dashboard__card--urgent');
    });

    it('does not list the members-only pages the wall refuses a friend', async () => {
      mount({
        user: makeUser({ kind: 'friend', membership: FRIEND }),
        status: FRIEND,
        config: { ...SITE_CONFIG, members_pages: [OPS_MANUAL] },
      });

      await screen.findByRole('heading', { name: 'You are a friend of CalDART' });
      expect(screen.queryByRole('heading', { name: 'Member content' })).not.toBeInTheDocument();
    });

    it('lists them for a friend whose staff role lets them read', async () => {
      mount({
        user: makeUser({ kind: 'friend', membership: FRIEND, roles: ['member', 'dart_leader'] }),
        status: FRIEND,
        config: { ...SITE_CONFIG, members_pages: [OPS_MANUAL] },
      });

      expect(await screen.findByRole('link', { name: 'Ops manual' })).toHaveAttribute(
        'href',
        OPS_MANUAL.url,
      );
    });
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
      kind: 'membership',
      amount_cents: 4500 + index,
      plan_amount_cents: 4500 + index,
      contribution_cents: 0,
      refunded_cents: 0,
      provider: 'stripe',
      wallet: 'card',
      status: 'succeeded',
      paid_on: `2026-0${index + 1}-01`,
      completed_at: `2026-0${index + 1}-01T12:00:00Z`,
      receipt_sent_at: `2026-0${index + 1}-01T12:00:05Z`,
      membership: null,
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

describe('DashboardPage · payments and renewal', () => {
  it('sends the member on to the payments screen for the rest', async () => {
    mount({ user: makeUser({ membership: CURRENT }), status: CURRENT });

    expect(
      await card('Recent payments').findByRole('link', {
        name: 'All payments, receipts and renewal',
      }),
    ).toHaveAttribute('href', '/payments');
  });

  it('says automatic renewal is off when the member has no mandate', async () => {
    mount({ user: makeUser({ membership: CURRENT }), status: CURRENT });

    expect(await screen.findByText('Automatic renewal is off.')).toBeInTheDocument();
  });

  it('names the next charge and its amount when automatic renewal is on', async () => {
    server.use(
      http.get(`${API}/me/renewal`, () =>
        HttpResponse.json({
          mandate: makeMandate({ next_charge_on: '2027-03-12', amount_cents: 7000 }),
        }),
      ),
    );
    mount({ user: makeUser({ membership: CURRENT }), status: CURRENT });

    const line = await screen.findByText(/Automatic renewal and contribution is on/);
    expect(within(line).getByText('$70.00')).toBeInTheDocument();
    expect(within(line).getByText('2027/03/12')).toBeInTheDocument();
  });

  it('says the contribution is off for a life member who has no mandate', async () => {
    mount({ user: makeUser({ membership: LIFETIME }), status: LIFETIME });

    expect(await screen.findByText('Automatic contribution is off.')).toBeInTheDocument();
  });

  it('names the next contribution and its amount for a life member', async () => {
    server.use(
      http.get(`${API}/me/renewal`, () =>
        HttpResponse.json({
          mandate: makeContributionMandate({ next_charge_on: '2027-08-20' }),
        }),
      ),
    );
    mount({ user: makeUser({ membership: LIFETIME }), status: LIFETIME });

    const line = await screen.findByText(/Automatic contribution is on/);
    expect(line).toHaveTextContent('Automatic contribution is on: $50.00 on 2027/08/20.');
  });

  it('says renewal stopped when a mandate has run out of retries', async () => {
    server.use(
      http.get(`${API}/me/renewal`, () =>
        HttpResponse.json({ mandate: makeMandate({ status: 'paused' }) }),
      ),
    );
    mount({ user: makeUser({ membership: CURRENT }), status: CURRENT });

    expect(
      await screen.findByText(/Automatic renewal and contribution stopped/),
    ).toBeInTheDocument();
  });
});

describe('DashboardPage · email verification', () => {
  const UNVERIFIED = makeUser({
    email: 'new@example.org',
    email_verified: false,
    membership: CURRENT,
  });

  it('asks a member with an unverified address to verify it, above everything else', async () => {
    mount({ user: UNVERIFIED, status: CURRENT });

    const heading = await screen.findByRole('heading', { name: 'Verify your email address' });
    const cards = Array.from(document.querySelectorAll('.col-text > section'));
    expect(cards[0]).toBe(heading.closest('section'));
  });

  it('says which address is unverified', async () => {
    mount({ user: UNVERIFIED, status: CURRENT });

    await screen.findByRole('heading', { name: 'Verify your email address' });
    expect(
      card('Verify your email address').getByText(
        'Your email address, new@example.org, is unverified until you click the link in the ' +
          'verification message we sent it.',
      ),
    ).toBeVisible();
  });

  it('marks the verification card as a nudge', async () => {
    mount({ user: UNVERIFIED, status: CURRENT });

    const heading = await screen.findByRole('heading', { name: 'Verify your email address' });
    expect(heading.closest('section')).toHaveClass('dashboard__nudge');
  });

  it('resends the message and says where it went', async () => {
    server.use(
      http.post(`${API}/auth/email/resend`, () =>
        HttpResponse.json(
          { detail: 'Verification message sent to new@example.org.' },
          { status: 202 },
        ),
      ),
    );
    mount({ user: UNVERIFIED, status: CURRENT });

    await screen.findByRole('heading', { name: 'Verify your email address' });
    card('Verify your email address')
      .getByRole('button', { name: 'Resend verification message' })
      .click();

    expect(await screen.findByText('Verification message sent to new@example.org.')).toBeVisible();
  });

  it('leaves a verified address alone', async () => {
    mount({ user: makeUser({ membership: CURRENT }), status: CURRENT });

    await screen.findByRole('heading', { name: 'Your membership is current' });
    expect(
      screen.queryByRole('heading', { name: 'Verify your email address' }),
    ).not.toBeInTheDocument();
  });
});
