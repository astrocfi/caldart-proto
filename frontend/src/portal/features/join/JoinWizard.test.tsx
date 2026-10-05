import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, delay, http } from 'msw';
import { Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { API, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type {
  MembershipDetail,
  MembershipStatus,
  PaymentsConfig,
  SiteConfig,
  User,
} from '@/portal/api/types';
import { TEST_DARTS, makeProfile } from '@test/fixtures/profile';
import { JoinWizard } from './JoinWizard';
import { FRIEND_PAY_KEY } from './steps';

// The wizard holds a friend's pay step open in this tab's session storage.
afterEach(() => window.sessionStorage.clear());

const SITE_CONFIG: SiteConfig = {
  org_name: 'CalDART',
  theme: 'sierra',
  contact_email: 'info@example.org',
  nav: [],
  members_pages: [{ title: 'Ops manual', url: '/members/ops-manual/' }],
};

const CURRENT: MembershipStatus = {
  status: 'current',
  expires_on: '2027-06-30',
  plan: 'Annual',
  is_lifetime: false,
};

/** What a joiner who has not paid reads as, whichever kind they chose: a friend. */
const UNPAID: MembershipStatus = {
  status: 'friend',
  expires_on: null,
  plan: null,
  is_lifetime: false,
};

/** The lede over a member's pay step. */
const MEMBER_PAY_LEDE =
  'Card, Apple Pay, Google Pay, or PayPal. Your membership starts immediately.';

/** The done step's sentence about the receipt a payment in this visit sent. */
const RECEIPT = /A receipt is on its way to your inbox/;

const CURRENT_DETAIL: MembershipDetail = { ...CURRENT, history: [] };

/** Enough of `GET /payments/config` for the pay step to render its one tab. */
const PAYMENTS_CONFIG: PaymentsConfig = {
  providers: ['mock'],
  stripe_publishable_key: '',
  paypal_client_id: '',
  plans: [
    {
      slug: 'annual',
      name: 'Annual',
      price_cents: 4500,
      duration_days: 365,
      description: 'Membership for one year.',
    },
  ],
  contribution_tiers: [{ label: 'No contribution', cents: 0 }],
  max_contribution_cents: 9_999_900,
};

const paymentsConfigHandler = () =>
  http.get(API + '/payments/config', () => HttpResponse.json(PAYMENTS_CONFIG));

/** Prints the current path so the redirects can be asserted on. */
function Path() {
  return <span data-testid="path">{useLocation().pathname}</span>;
}

function renderWizard(route: string) {
  return renderWithProviders(
    <>
      <Path />
      <Routes>
        <Route path="/join" element={<JoinWizard />} />
        <Route path="/join/:step" element={<JoinWizard />} />
        <Route path="/" element={<h1>Dashboard</h1>} />
      </Routes>
    </>,
    { route },
  );
}

function path(): string {
  return screen.getByTestId('path').textContent ?? '';
}

/** Everything the wizard's five steps might ask for. */
function stubApi(user: User | null) {
  server.use(
    user
      ? signedInAs(user)
      : http.get(`${API}/auth/me`, () =>
          HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 }),
        ),
    http.get(`${API}/darts`, () => HttpResponse.json(TEST_DARTS)),
    http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile())),
    http.get(`${API}/me/membership`, () => HttpResponse.json(CURRENT_DETAIL)),
    http.get(`${API}/site/config`, () => HttpResponse.json(SITE_CONFIG)),
    paymentsConfigHandler(),
  );
}

describe('<JoinWizard/> resume logic', () => {
  it('starts a visitor with no account on step 1', async () => {
    stubApi(null);
    renderWizard('/join');

    expect(await screen.findByRole('heading', { name: 'Create your account' })).toBeInTheDocument();
    expect(path()).toBe('/join/account');
  });

  it('names the browser tab Join', async () => {
    stubApi(null);
    renderWizard('/join');

    await screen.findByRole('heading', { name: 'Create your account' });
    expect(document.title).toBe('Join · CalDART');
  });

  it('resumes a signed-in visitor with an unverified address on the verify step', async () => {
    stubApi(makeUser({ email_verified: false, profile_complete: false, membership: UNPAID }));
    renderWizard('/join');

    expect(await screen.findByRole('heading', { name: 'Check your email' })).toBeInTheDocument();
    expect(path()).toBe('/join/verify');
  });

  it('skips the verify step for an address that is already verified', async () => {
    stubApi(makeUser({ profile_complete: false, membership: UNPAID }));
    renderWizard('/join/verify');

    expect(await screen.findByRole('heading', { name: 'About you' })).toBeInTheDocument();
    expect(path()).toBe('/join/profile');
  });

  it('resumes a signed-in member with a thin profile on the profile step', async () => {
    stubApi(makeUser({ profile_complete: false, membership: UNPAID }));
    renderWizard('/join');

    expect(await screen.findByRole('heading', { name: 'About you' })).toBeInTheDocument();
    expect(path()).toBe('/join/profile');
  });

  it('resumes a member-intent joiner who has not paid on the pay step', async () => {
    stubApi(makeUser({ kind: 'member', profile_complete: true, membership: UNPAID }));
    renderWizard('/join');

    expect(await screen.findByRole('heading', { name: 'Pay your dues' })).toBeInTheDocument();
    expect(path()).toBe('/join/pay');
  });

  it('offers a member-intent joiner no Not now on the pay step', async () => {
    stubApi(makeUser({ kind: 'member', profile_complete: true, membership: UNPAID }));
    renderWizard('/join/pay');

    await screen.findByRole('heading', { name: 'Pay your dues' });
    expect(screen.queryByRole('button', { name: 'Not now' })).not.toBeInTheDocument();
  });

  it('resumes a paid-up member on the done step', async () => {
    stubApi(makeUser());
    renderWizard('/join');

    expect(await screen.findByRole('heading', { name: 'Welcome to CalDART' })).toBeInTheDocument();
    expect(path()).toBe('/join/done');
  });

  it('refuses to let a visitor skip ahead to paying', async () => {
    stubApi(null);
    renderWizard('/join/pay');

    expect(await screen.findByRole('heading', { name: 'Create your account' })).toBeInTheDocument();
    expect(path()).toBe('/join/account');
  });

  it('lets a member who has not paid go back to an earlier step', async () => {
    stubApi(makeUser({ kind: 'member', membership: UNPAID }));
    renderWizard('/join/profile');

    expect(await screen.findByRole('heading', { name: 'About you' })).toBeInTheDocument();
    expect(path()).toBe('/join/profile');
  });

  it('sends an unknown step back to where the visitor belongs', async () => {
    stubApi(makeUser());
    renderWizard('/join/nonsense');

    await waitFor(() => expect(path()).toBe('/join/done'));
  });
});

describe('<JoinWizard/> for somebody who has joined already', () => {
  it.each(['profile', 'pay'])(
    'sends a paid member who browses back to the %s step to the dashboard',
    async (step) => {
      stubApi(makeUser({ membership: CURRENT }));
      renderWizard(`/join/${step}`);

      expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
      expect(path()).toBe('/');
    },
  );

  it('sends a friend who has joined to the dashboard from the pay step', async () => {
    stubApi(makeUser({ kind: 'friend', membership: UNPAID }));
    renderWizard('/join/pay');

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
  });

  it('ignores a pay-step hold left in the tab for a paid member', async () => {
    window.sessionStorage.setItem(FRIEND_PAY_KEY, String(makeUser().id));
    stubApi(makeUser({ membership: CURRENT }));
    renderWizard('/join/pay');

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
  });

  it('holds nobody but a friend at the pay step', async () => {
    stubApi(makeUser({ kind: 'member', profile_complete: false, membership: UNPAID }));
    server.use(http.put(`${API}/me/profile`, () => HttpResponse.json(makeProfile())));
    renderWizard('/join/profile');

    await userEvent.click(await screen.findByRole('button', { name: 'Save and continue' }));
    await screen.findByRole('heading', { name: 'Pay your dues' });

    expect(window.sessionStorage.getItem(FRIEND_PAY_KEY)).toBeNull();
  });
});

describe('<JoinWizard/> layout', () => {
  it('wraps the header and the step list in the centered join shell', async () => {
    stubApi(null);
    const { container } = renderWizard('/join/account');

    await screen.findByRole('heading', { name: 'Create your account' });
    const shell = container.querySelector('.join-shell');
    expect(shell).not.toBeNull();
    expect(shell?.querySelector('.page__header')).not.toBeNull();
    expect(shell?.querySelector('.join-steps')).not.toBeNull();
  });

  it.each([
    ['account', null, 'Create your account'],
    ['profile', makeUser({ profile_complete: false, membership: UNPAID }), 'About you'],
    ['pay', makeUser({ kind: 'member', membership: UNPAID }), 'Pay your dues'],
  ])('draws the %s step at the wizard’s one width', async (step, user, heading) => {
    stubApi(user);
    const { container } = renderWizard(`/join/${step}`);

    const card = (await screen.findByRole('heading', { name: heading })).closest('.card');
    expect(card?.className).toBe('card join-card');
    expect(container.querySelector('.join-shell')?.className).toBe('join-shell');
  });

  it('shows the step once, in the progress list, with no eyebrow over the card', async () => {
    stubApi(null);
    renderWizard('/join/account');

    await screen.findByRole('heading', { name: 'Create your account' });
    expect(screen.queryByText(/Step 1 of 5/)).not.toBeInTheDocument();
  });
});

describe('<JoinWizard/> progress', () => {
  beforeEach(() => stubApi(null));

  it('marks the current step and leaves the rest to do', async () => {
    renderWizard('/join/account');

    const steps = await screen.findByRole('list', { name: 'Join progress' });
    const [account, verify] = Array.from(steps.querySelectorAll('li'));
    expect(account).toHaveAttribute('data-state', 'current');
    expect(account).toHaveAttribute('aria-current', 'step');
    expect(verify).toHaveAttribute('data-state', 'todo');
  });

  it('names all five steps', async () => {
    renderWizard('/join/account');

    const steps = await screen.findByRole('list', { name: 'Join progress' });
    expect(Array.from(steps.querySelectorAll('li')).map((li) => li.textContent)).toEqual([
      'Account',
      'Verify',
      'Profile',
      'Pay',
      'Done',
    ]);
  });
});

describe('<JoinWizard/> step progression', () => {
  beforeEach(() => {
    server.use(
      http.get(`${API}/darts`, () => HttpResponse.json(TEST_DARTS)),
      http.get(`${API}/me/membership`, () => HttpResponse.json(CURRENT_DETAIL)),
      http.get(`${API}/site/config`, () => HttpResponse.json(SITE_CONFIG)),
      paymentsConfigHandler(),
    );
  });

  it('registers an account and asks for the address to be verified', async () => {
    let registered: unknown = null;
    let user: User | null = null;
    server.use(
      http.get(`${API}/auth/me`, () =>
        user ? HttpResponse.json(user) : HttpResponse.json({ detail: 'no' }, { status: 401 }),
      ),
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile({ phone: '' }))),
      http.post(`${API}/auth/register`, async ({ request }) => {
        registered = await request.json();
        user = makeUser({ email_verified: false, profile_complete: false, membership: UNPAID });
        return HttpResponse.json(user, { status: 201 });
      }),
    );

    renderWizard('/join');

    await screen.findByRole('heading', { name: 'Create your account' });
    await userEvent.type(screen.getByLabelText(/^First name/), 'Marta');
    await userEvent.type(screen.getByLabelText(/^Last name/), 'Reyes');
    await userEvent.type(screen.getByLabelText(/^Email address/), 'marta@example.org');
    await userEvent.type(screen.getByLabelText(/^Password/), 'a-good-password');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));

    expect(await screen.findByRole('heading', { name: 'Check your email' })).toBeInTheDocument();
    expect(path()).toBe('/join/verify');
    expect(registered).toEqual({
      first_name: 'Marta',
      last_name: 'Reyes',
      email: 'marta@example.org',
      password: 'a-good-password',
      kind: 'member',
    });
  });

  it('moves on to the profile step once the address is verified', async () => {
    let user = makeUser({ email_verified: false, profile_complete: false, membership: UNPAID });
    server.use(
      http.get(`${API}/auth/me`, () => HttpResponse.json(user)),
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile({ phone: '' }))),
    );

    renderWizard('/join/verify');

    await screen.findByRole('heading', { name: 'Check your email' });
    user = { ...user, email_verified: true };
    await userEvent.click(screen.getByRole('button', { name: "I've clicked the link" }));

    expect(await screen.findByRole('heading', { name: 'About you' })).toBeInTheDocument();
    expect(path()).toBe('/join/profile');
  });

  it('shows what the register endpoint rejected', async () => {
    server.use(
      http.get(`${API}/auth/me`, () => HttpResponse.json({ detail: 'no' }, { status: 401 })),
      http.post(`${API}/auth/register`, () =>
        HttpResponse.json({ email: 'That address is already registered.' }, { status: 400 }),
      ),
    );

    renderWizard('/join/account');

    await screen.findByRole('heading', { name: 'Create your account' });
    await userEvent.type(screen.getByLabelText(/^First name/), 'Marta');
    await userEvent.type(screen.getByLabelText(/^Last name/), 'Reyes');
    await userEvent.type(screen.getByLabelText(/^Email address/), 'taken@example.org');
    await userEvent.type(screen.getByLabelText(/^Password/), 'a-good-password');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));

    expect(await screen.findByText('That address is already registered.')).toBeInTheDocument();
    expect(path()).toBe('/join/account');
  });

  it('offers to continue when the visitor is already signed in', async () => {
    stubApi(makeUser({ profile_complete: false, membership: UNPAID }));
    renderWizard('/join/account');

    await screen.findByRole('heading', { name: 'Your account' });
    expect(screen.getByText('member@example.org')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }));

    expect(await screen.findByRole('heading', { name: 'About you' })).toBeInTheDocument();
  });

  it('saves the profile and moves on to paying', async () => {
    let saved: Record<string, unknown> | null = null;
    server.use(
      signedInAs(makeUser({ profile_complete: false, membership: UNPAID })),
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile())),
      http.put(`${API}/me/profile`, async ({ request }) => {
        saved = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(makeProfile());
      }),
    );

    renderWizard('/join');

    await screen.findByRole('heading', { name: 'About you' });
    await userEvent.click(await screen.findByRole('button', { name: 'Save and continue' }));

    expect(await screen.findByRole('heading', { name: 'Pay your dues' })).toBeInTheDocument();
    expect(path()).toBe('/join/pay');
    expect(saved).toMatchObject({ phone: '650-555-0101', city: 'San Carlos' });
  });

  it('stays on the profile step while the form is invalid', async () => {
    server.use(
      signedInAs(makeUser({ profile_complete: false, membership: UNPAID })),
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile({ city: '' }))),
    );

    renderWizard('/join');

    await screen.findByRole('heading', { name: 'About you' });
    await userEvent.click(await screen.findByRole('button', { name: 'Save and continue' }));

    expect(await screen.findByText('Enter your city.')).toBeInTheDocument();
    expect(path()).toBe('/join/profile');
  });

  it('celebrates on the last step and links onwards', async () => {
    stubApi(makeUser());
    renderWizard('/join/done');

    await screen.findByRole('heading', { name: 'Welcome to CalDART' });
    expect(screen.getByRole('link', { name: 'Go to my dashboard' })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: 'Add the planes I fly' })).toHaveAttribute(
      'href',
      '/profile/aircraft',
    );
    expect(screen.getByRole('link', { name: 'Ops manual' })).toHaveAttribute(
      'href',
      '/members/ops-manual/',
    );
  });

  it('promises no receipt to a member who did not pay in this visit', async () => {
    stubApi(makeUser());
    renderWizard('/join/done');

    await screen.findByRole('heading', { name: 'Welcome to CalDART' });
    expect(screen.queryByText(RECEIPT)).not.toBeInTheDocument();
  });
});

describe('<JoinWizard/> returning from a redirect payment', () => {
  /** What Stripe's `return_url` looks like when the browser comes back. */
  const RETURN = '/join/done?payment_id=42&payment_intent=pi_1';

  it('confirms the payment on /join/done instead of bouncing back to pay', async () => {
    let confirmed: Record<string, unknown> | null = null;
    // The server has not activated the membership yet — exactly the state the
    // wizard used to read as "you still owe us the fee".
    let user = makeUser({ profile_complete: true, membership: UNPAID });
    server.use(
      http.get(`${API}/auth/me`, () => HttpResponse.json(user)),
      http.get(`${API}/me/membership`, () => HttpResponse.json(CURRENT_DETAIL)),
      http.get(`${API}/site/config`, () => HttpResponse.json(SITE_CONFIG)),
      http.post(`${API}/payments/stripe/confirm`, async ({ request }) => {
        confirmed = (await request.json()) as Record<string, unknown>;
        user = makeUser({ profile_complete: true, membership: CURRENT });
        return HttpResponse.json({ status: 'succeeded', membership: CURRENT });
      }),
    );

    renderWizard(RETURN);

    // Step 5 arrives only once the payment has settled.
    expect(await screen.findByRole('heading', { name: 'Welcome to CalDART' })).toBeInTheDocument();
    expect(confirmed).toEqual({ payment_id: 42, payment_intent_id: 'pi_1' });
    expect(await screen.findByText(RECEIPT)).toBeInTheDocument();
    // …and the payment reference is spent, so a refresh cannot replay it.
    await waitFor(() => expect(path()).toBe('/join/done'));
  });

  it('says a member is almost there while their paid membership is not visible yet', async () => {
    const user = makeUser({ profile_complete: true, membership: UNPAID });
    server.use(
      signedInAs(user),
      // The settled term has not reached the membership read yet, so it still says friend.
      http.get(`${API}/me/membership`, () => HttpResponse.json({ ...UNPAID, history: [] })),
      http.get(`${API}/site/config`, () => HttpResponse.json(SITE_CONFIG)),
      http.post(`${API}/payments/stripe/confirm`, () =>
        HttpResponse.json({ status: 'succeeded', membership: CURRENT }),
      ),
    );

    renderWizard(RETURN);

    await screen.findByText('Your membership is not active yet.');
    expect(screen.getByRole('heading', { name: 'Almost there' })).toBeInTheDocument();
  });

  it('offers a way back to paying when the payment was declined', async () => {
    server.use(
      signedInAs(makeUser({ profile_complete: true, membership: UNPAID })),
      http.get(`${API}/me/membership`, () => HttpResponse.json(CURRENT_DETAIL)),
      http.get(`${API}/site/config`, () => HttpResponse.json(SITE_CONFIG)),
      http.post(`${API}/payments/stripe/confirm`, () =>
        HttpResponse.json({ detail: 'Not confirmed' }, { status: 400 }),
      ),
      http.get(`${API}/payments/42`, () =>
        HttpResponse.json({ status: 'failed', membership: UNPAID }),
      ),
    );

    renderWizard(RETURN);

    expect(await screen.findByText(/declined/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to payment' })).toHaveAttribute(
      'href',
      '/join/pay',
    );
  });

  it('ignores a payment reference from someone with no session', async () => {
    stubApi(null);
    renderWizard(RETURN);

    expect(await screen.findByRole('heading', { name: 'Create your account' })).toBeInTheDocument();
    expect(path()).toBe('/join/account');
  });
});

describe('<JoinWizard/> for a friend', () => {
  const FRIEND: MembershipStatus = UNPAID;
  const FRIEND_DETAIL: MembershipDetail = { ...FRIEND, history: [] };

  /** The pay step's config with a tier to give, since a friend's checkout has no plan. */
  const GIVING_CONFIG: PaymentsConfig = {
    ...PAYMENTS_CONFIG,
    contribution_tiers: [
      { label: 'No contribution', cents: 0 },
      { label: 'Participating', cents: 2000 },
    ],
  };

  function makeFriend(overrides: Partial<User> = {}): User {
    return makeUser({ kind: 'friend', membership: FRIEND, ...overrides });
  }

  function stubFriendApi(user: User): void {
    stubApi(user);
    server.use(
      http.get(`${API}/me/membership`, () => HttpResponse.json(FRIEND_DETAIL)),
      http.get(`${API}/payments/config`, () => HttpResponse.json(GIVING_CONFIG)),
    );
  }

  it('asks a friend for a contribution on the way through from the profile', async () => {
    stubFriendApi(makeFriend({ profile_complete: false }));
    server.use(http.put(`${API}/me/profile`, () => HttpResponse.json(makeProfile())));
    renderWizard('/join');

    await screen.findByRole('heading', { name: 'About you' });
    await userEvent.click(await screen.findByRole('button', { name: 'Save and continue' }));

    expect(await screen.findByRole('heading', { name: 'Donate to CalDART' })).toBeInTheDocument();
    expect(path()).toBe('/join/pay');
    // A friend's checkout sells no plan.
    expect(await screen.findByRole('radio', { name: /Participating/ })).toBeInTheDocument();
    expect(screen.queryByRole('radio', { name: /Annual/ })).not.toBeInTheDocument();
  });

  it('lets a friend go on without giving', async () => {
    stubFriendApi(makeFriend({ profile_complete: false }));
    server.use(http.put(`${API}/me/profile`, () => HttpResponse.json(makeProfile())));
    renderWizard('/join');

    await userEvent.click(await screen.findByRole('button', { name: 'Save and continue' }));
    await screen.findByRole('radio', { name: /Participating/ });
    await userEvent.click(screen.getByRole('button', { name: 'Continue without a gift' }));

    expect(await screen.findByRole('heading', { name: 'Welcome to CalDART' })).toBeInTheDocument();
    expect(path()).toBe('/join/done');
  });

  it('promises no receipt to a friend who gave nothing', async () => {
    stubFriendApi(makeFriend({ profile_complete: false }));
    server.use(http.put(`${API}/me/profile`, () => HttpResponse.json(makeProfile())));
    renderWizard('/join');

    await userEvent.click(await screen.findByRole('button', { name: 'Save and continue' }));
    await screen.findByRole('radio', { name: /Participating/ });
    await userEvent.click(screen.getByRole('button', { name: 'Continue without a gift' }));

    await screen.findByText(
      'You are a friend of CalDART: no dues, no expiry. Become a member any time.',
    );
    expect(screen.queryByText(/receipt/)).not.toBeInTheDocument();
  });

  it('moves on to done once the contribution is paid', async () => {
    stubFriendApi(makeFriend({ profile_complete: false }));
    server.use(
      http.put(`${API}/me/profile`, () => HttpResponse.json(makeProfile())),
      http.post(`${API}/payments/checkout`, () =>
        HttpResponse.json({ payment_id: 5, provider: 'mock', client: {} }, { status: 201 }),
      ),
      http.post(`${API}/payments/mock/complete`, () =>
        HttpResponse.json({ status: 'succeeded', membership: FRIEND }),
      ),
    );
    renderWizard('/join');

    await userEvent.click(await screen.findByRole('button', { name: 'Save and continue' }));
    await userEvent.click(await screen.findByRole('radio', { name: /Participating/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Succeed' }));

    expect(await screen.findByRole('heading', { name: 'Welcome to CalDART' })).toBeInTheDocument();
    expect(path()).toBe('/join/done');
    expect(await screen.findByText(RECEIPT)).toBeInTheDocument();
  });

  it('keeps a friend on the pay step through a reload until they go on', async () => {
    stubFriendApi(makeFriend({ profile_complete: false }));
    server.use(http.put(`${API}/me/profile`, () => HttpResponse.json(makeProfile())));
    const first = renderWizard('/join');

    await userEvent.click(await screen.findByRole('button', { name: 'Save and continue' }));
    await screen.findByRole('heading', { name: 'Donate to CalDART' });
    first.unmount();
    stubFriendApi(makeFriend());
    renderWizard('/join/pay');

    expect(await screen.findByRole('heading', { name: 'Donate to CalDART' })).toBeInTheDocument();
    expect(path()).toBe('/join/pay');
  });

  it('lets the pay step go once the friend continues without a gift', async () => {
    stubFriendApi(makeFriend({ profile_complete: false }));
    server.use(http.put(`${API}/me/profile`, () => HttpResponse.json(makeProfile())));
    renderWizard('/join');

    await userEvent.click(await screen.findByRole('button', { name: 'Save and continue' }));
    await screen.findByRole('radio', { name: /Participating/ });
    await userEvent.click(screen.getByRole('button', { name: 'Continue without a gift' }));

    await screen.findByRole('heading', { name: 'Welcome to CalDART' });
    expect(window.sessionStorage.getItem(FRIEND_PAY_KEY)).toBeNull();
  });

  it('resumes a friend with a complete profile on the done step, not the pay step', async () => {
    stubFriendApi(makeFriend());
    renderWizard('/join');

    expect(await screen.findByRole('heading', { name: 'Welcome to CalDART' })).toBeInTheDocument();
    expect(path()).toBe('/join/done');
  });

  it('tells a friend what being one means on the done step', async () => {
    stubFriendApi(makeFriend());
    renderWizard('/join/done');

    expect(
      await screen.findByText(
        'You are a friend of CalDART: no dues, no expiry. Become a member any time.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('Friend')).toBeInTheDocument();
    // Members-only pages are for members; the wizard does not offer them to a friend.
    expect(screen.queryByRole('link', { name: 'Ops manual' })).not.toBeInTheDocument();
  });

  it('says a friend is joining as one in the lede', async () => {
    stubFriendApi(makeFriend());
    renderWizard('/join/done');

    expect(await screen.findByText('You are a friend of CalDART.')).toBeInTheDocument();
  });
});

describe('<JoinWizard/> ledes', () => {
  it('names no prices before the pay step', async () => {
    stubApi(null);
    renderWizard('/join/account');

    expect(await screen.findByText('Joining takes about three minutes.')).toBeInTheDocument();
  });

  it('says nothing else is available until the address is verified', async () => {
    stubApi(makeUser({ email_verified: false, profile_complete: false, membership: UNPAID }));
    renderWizard('/join/verify');

    expect(
      await screen.findByText(
        'Nothing else in the portal is available until you verify your email address.',
      ),
    ).toBeInTheDocument();
  });

  it('welcomes a member to CalDART by its short name', async () => {
    stubApi(makeUser());
    renderWizard('/join/done');

    expect(await screen.findByText('You are a member of CalDART.')).toBeInTheDocument();
  });
});

describe('<JoinWizard/> for a member who changes their mind', () => {
  const FRIEND_LINK = 'Join as a friend instead (no dues)';

  function stubChangeOfMind(): void {
    stubApi(makeUser({ kind: 'member', membership: UNPAID }));
    server.use(
      http.post(`${API}/me/kind/friend`, () =>
        HttpResponse.json(makeUser({ kind: 'friend', membership: UNPAID })),
      ),
      http.get(`${API}/me/membership`, () => HttpResponse.json({ ...UNPAID, history: [] })),
    );
  }

  it('offers a quiet way to be a friend instead, not a plan to choose', async () => {
    stubChangeOfMind();
    renderWizard('/join/pay');

    expect(await screen.findByRole('button', { name: FRIEND_LINK })).toBeInTheDocument();
    expect(screen.queryByRole('radio', { name: /friend/i })).not.toBeInTheDocument();
  });

  it('turns the step into a friend’s donation', async () => {
    stubChangeOfMind();
    renderWizard('/join/pay');

    await userEvent.click(await screen.findByRole('button', { name: FRIEND_LINK }));

    expect(screen.getByRole('heading', { name: 'Donate to CalDART' })).toBeInTheDocument();
    expect(path()).toBe('/join/pay');
  });

  it('reaches the done step as a friend after continuing without a gift', async () => {
    stubChangeOfMind();
    renderWizard('/join/pay');

    await userEvent.click(await screen.findByRole('button', { name: FRIEND_LINK }));
    await userEvent.click(await screen.findByRole('button', { name: 'Continue without a gift' }));

    expect(await screen.findByText('You are a friend of CalDART.')).toBeInTheDocument();
    expect(path()).toBe('/join/done');
  });
});

describe('<JoinWizard/> for a friend who changes their mind', () => {
  const MEMBER_BUTTON = 'I changed my mind, I want to be a member';

  /** A stored friend on the pay step the wizard holds for them, whose payment makes them a current member. */
  function stubFriendToMember(): void {
    let user = makeUser({ kind: 'friend', membership: UNPAID });
    window.sessionStorage.setItem(FRIEND_PAY_KEY, String(user.id));
    stubApi(user);
    server.use(
      http.get(`${API}/auth/me`, () => HttpResponse.json(user)),
      http.post(`${API}/payments/checkout`, () =>
        HttpResponse.json({ payment_id: 5, provider: 'mock', client: {} }, { status: 201 }),
      ),
      http.post(`${API}/payments/mock/complete`, () => {
        user = makeUser({ kind: 'member', membership: CURRENT });
        return HttpResponse.json({ status: 'succeeded', membership: CURRENT });
      }),
    );
  }

  it('shows the dues checkout and the member’s lede', async () => {
    stubFriendToMember();
    renderWizard('/join/pay');

    await userEvent.click(await screen.findByRole('button', { name: MEMBER_BUTTON }));

    expect(screen.getByRole('heading', { name: 'Pay your dues' })).toBeInTheDocument();
    expect(screen.getByText(MEMBER_PAY_LEDE)).toBeInTheDocument();
  });

  it('reaches the done step as a member once the dues are paid', async () => {
    stubFriendToMember();
    renderWizard('/join/pay');

    await userEvent.click(await screen.findByRole('button', { name: MEMBER_BUTTON }));
    // Hold the account's refetch, so the cached friend is all the done step could read.
    server.use(
      http.get(`${API}/auth/me`, async () => {
        await delay('infinite');
        return HttpResponse.json(null);
      }),
    );
    await userEvent.click(await screen.findByRole('button', { name: 'Succeed' }));

    expect(await screen.findByText('You are a member of CalDART.')).toBeInTheDocument();
    expect(path()).toBe('/join/done');
    await waitFor(() =>
      expect(screen.queryByText('Checking your membership…')).not.toBeInTheDocument(),
    );
    expect(screen.queryByText(/You are a friend of CalDART: no dues/)).not.toBeInTheDocument();
  });
});
