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
import { EXPIRING_WINDOW_DAYS } from '@/portal/components/StatusDot';
import { DashboardPage, quickLinks } from './DashboardPage';

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

const FRIEND: MembershipStatus = {
  status: 'friend',
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

  it('gives a member who registered and never paid the friend card', async () => {
    mount({ user: makeUser({ kind: 'member', membership: FRIEND }), status: FRIEND });

    await screen.findByRole('heading', { name: 'You are a friend of CalDART' });
    const status = card('You are a friend of CalDART');
    expect(status.getByRole('link', { name: 'Make me a member' })).toHaveAttribute(
      'href',
      '/membership/join',
    );
    expect(status.queryByRole('link', { name: 'Join CalDART' })).not.toBeInTheDocument();
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
          'No dues and no expiry. Become a member any time.',
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

    it('offers Donate rather than Renew in the quick links', async () => {
      mountFriend();

      await screen.findByRole('heading', { name: 'You are a friend of CalDART' });
      const links = card('Quick links');
      expect(links.queryByRole('link', { name: 'Renew' })).not.toBeInTheDocument();
      expect(links.getByRole('link', { name: 'Donate' })).toHaveAttribute('href', '/donate');
    });

    it('says nothing about a renewal a friend cannot have', async () => {
      mountFriend();

      await screen.findByRole('heading', { name: 'You are a friend of CalDART' });
      expect(screen.queryByText(/Automatic renewal/)).not.toBeInTheDocument();
      expect(
        card('Recent payments').getByRole('link', { name: 'All payments and receipts' }),
      ).toHaveAttribute('href', '/payments');
    });

    it('names a friend’s recurring donation when there is one', async () => {
      server.use(
        http.get(`${API}/me/donation`, () =>
          HttpResponse.json({
            mandate: makeContributionMandate({ next_charge_on: '2027-08-20' }),
          }),
        ),
      );
      mountFriend();

      expect(await screen.findByText(/Recurring donation is on/)).toHaveTextContent(
        'Recurring donation is on: $50.00 will be charged on 08/20/2027.',
      );
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

  it('offers an account administrator their own tasks among the quick links', async () => {
    mount({
      user: makeUser({ membership: CURRENT, roles: ['member', 'account_admin'] }),
      status: CURRENT,
    });

    // The links are role-filtered, so wait until `/auth/me` has actually landed.
    await screen.findByRole('heading', { name: 'Welcome, Marta' });
    const names = card('Quick links')
      .getAllByRole('link')
      .map((link) => link.textContent);
    expect(names).toEqual(['Renew', 'My profile', 'Member check', 'Finance', 'Members']);
  });

  it('offers a plain member four next steps, not the whole menu', async () => {
    mount({ user: makeUser({ membership: CURRENT }), status: CURRENT });

    await screen.findByRole('heading', { name: 'Welcome, Marta' });
    const names = card('Quick links')
      .getAllByRole('link')
      .map((link) => link.textContent);
    expect(names).toEqual(['Renew', 'My profile', 'My aircraft', 'Messages']);
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

  it('tells a lapsed member that renewing opens the members-only pages again', async () => {
    mount({ user: makeUser({ membership: EXPIRED }), status: EXPIRED });

    const link = await screen.findByRole('link', { name: 'Renew to read them again.' });
    expect(link).toHaveAttribute('href', '/renew');
  });

  it('does not tell a lapsed member that nothing is published', async () => {
    mount({ user: makeUser({ membership: EXPIRED }), status: EXPIRED });

    await screen.findByRole('link', { name: 'Renew to read them again.' });
    expect(screen.queryByText('Nothing published yet')).not.toBeInTheDocument();
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

  it('dates a recent payment by the day it was paid, as Payments does', async () => {
    const payment: PaymentSummary = {
      id: 7,
      plan: 'Annual',
      kind: 'membership',
      amount_cents: 4500,
      plan_amount_cents: 4500,
      contribution_cents: 0,
      refunded_cents: 0,
      provider: 'stripe',
      wallet: 'card',
      status: 'succeeded',
      paid_on: '2026-04-28',
      completed_at: '2026-04-29T02:52:00Z',
      receipt_sent_at: '2026-04-29T02:52:05Z',
      membership: null,
    };

    mount({ user: makeUser({ membership: CURRENT }), status: CURRENT, payments: [payment] });

    expect(await card('Recent payments').findByText('04/28/2026')).toBeInTheDocument();
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
        name: 'All payments, receipts, and renewals',
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

    const line = await screen.findByText(/Automatic renewal is on/);
    expect(line).toHaveTextContent('Automatic renewal is on: $70.00 will be charged on 03/12/2027.');
  });

  it('says the recurring donation is off for a life member who has none', async () => {
    mount({ user: makeUser({ membership: LIFETIME }), status: LIFETIME });

    expect(await screen.findByText('Recurring donation is off.')).toBeInTheDocument();
  });

  it('names the next gift and its amount for a life member', async () => {
    server.use(
      http.get(`${API}/me/donation`, () =>
        HttpResponse.json({
          mandate: makeContributionMandate({ next_charge_on: '2027-08-20' }),
        }),
      ),
    );
    mount({ user: makeUser({ membership: LIFETIME }), status: LIFETIME });

    const line = await screen.findByText(/Recurring donation is on/);
    expect(line).toHaveTextContent(
      'Recurring donation is on: $50.00 will be charged on 08/20/2027.',
    );
  });

  it('says renewal stopped when a mandate has run out of retries', async () => {
    server.use(
      http.get(`${API}/me/renewal`, () =>
        HttpResponse.json({ mandate: makeMandate({ status: 'paused' }) }),
      ),
    );
    mount({ user: makeUser({ membership: CURRENT }), status: CURRENT });

    expect(
      await screen.findByText(/Automatic renewal stopped after a payment was refused/),
    ).toBeInTheDocument();
  });
});

describe('DashboardPage · switching kinds', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it.each([
    [CURRENT, 'Your membership is current'],
    [EXPIRED, 'Your membership has expired'],
  ])('leaves Make me a friend to My profile, away from Renew', async (status, heading) => {
    mount({ user: makeUser({ membership: status }), status });

    await screen.findByRole('heading', { name: heading });
    expect(card(heading).queryByRole('button', { name: 'Make me a friend' })).toBeNull();
    expect(card(heading).getByRole('link', { name: 'Update your details' })).toHaveAttribute(
      'href',
      '/profile',
    );
  });

  it('never offers a life member Make me a friend', async () => {
    mount({ user: makeUser({ membership: LIFETIME }), status: LIFETIME });

    await screen.findByRole('heading', { name: 'Lifetime member' });
    expect(
      card('Lifetime member').queryByRole('button', { name: 'Make me a friend' }),
    ).not.toBeInTheDocument();
  });

  it('shows a pending change with its day and an Undo button', async () => {
    const user = makeUser({ membership: CURRENT, friend_on: isoIn(201) });
    mount({ user, status: CURRENT });

    await screen.findByRole('heading', { name: 'Your membership is current' });
    const status = card('Your membership is current');
    const [year, month, day] = isoIn(201).split('-');
    expect(
      await status.findByText(`You become a friend on ${month}/${day}/${year}.`),
    ).toBeInTheDocument();
    expect(status.getByRole('button', { name: 'Undo' })).toBeInTheDocument();
  });
});

describe('quickLinks', () => {
  /** The labels of the quick links for `roles`. */
  function labels(roles: Parameters<typeof quickLinks>[0], reader = {}): string[] {
    return quickLinks(roles, reader).map((item) => item.label);
  }

  it('adds Member check for a DART leader', () => {
    expect(labels(['member', 'dart_leader'])).toEqual([
      'Renew',
      'My profile',
      'My aircraft',
      'Messages',
      'Member check',
    ]);
  });

  it('adds Finance for a treasurer', () => {
    expect(labels(['member', 'treasurer'])).toEqual([
      'Renew',
      'My profile',
      'My aircraft',
      'Messages',
      'Finance',
    ]);
  });

  it('keeps a system administrator to five, their tasks first to stay', () => {
    expect(labels(['member', 'system_admin'])).toEqual([
      'Renew',
      'My profile',
      'Member check',
      'Finance',
      'Members',
    ]);
  });

  it('offers a life member Donate in place of Renew', () => {
    expect(labels(['member'], { isLifetime: true })[0]).toBe('Donate');
  });
});
