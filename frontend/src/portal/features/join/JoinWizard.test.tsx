import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

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

const NONE: MembershipStatus = {
  status: 'none',
  expires_on: null,
  plan: null,
  is_lifetime: false,
};

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

  it('resumes a signed-in visitor with an unverified address on the verify step', async () => {
    stubApi(makeUser({ email_verified: false, profile_complete: false, membership: NONE }));
    renderWizard('/join');

    expect(await screen.findByRole('heading', { name: 'Check your email' })).toBeInTheDocument();
    expect(path()).toBe('/join/verify');
  });

  it('skips the verify step for an address that is already verified', async () => {
    stubApi(makeUser({ profile_complete: false, membership: NONE }));
    renderWizard('/join/verify');

    expect(await screen.findByRole('heading', { name: 'About you' })).toBeInTheDocument();
    expect(path()).toBe('/join/profile');
  });

  it('resumes a signed-in member with a thin profile on the profile step', async () => {
    stubApi(makeUser({ profile_complete: false, membership: NONE }));
    renderWizard('/join');

    expect(await screen.findByRole('heading', { name: 'About you' })).toBeInTheDocument();
    expect(path()).toBe('/join/profile');
  });

  it('resumes a complete profile without a membership on the pay step', async () => {
    stubApi(makeUser({ profile_complete: true, membership: NONE }));
    renderWizard('/join');

    expect(await screen.findByRole('heading', { name: 'Pay your dues' })).toBeInTheDocument();
    expect(path()).toBe('/join/pay');
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

  it('lets a member go back to an earlier step', async () => {
    stubApi(makeUser());
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
        user = makeUser({ email_verified: false, profile_complete: false, membership: NONE });
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
    let user = makeUser({ email_verified: false, profile_complete: false, membership: NONE });
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
    stubApi(makeUser({ profile_complete: false, membership: NONE }));
    renderWizard('/join/account');

    await screen.findByRole('heading', { name: 'Your account' });
    expect(screen.getByText('member@example.org')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }));

    expect(await screen.findByRole('heading', { name: 'About you' })).toBeInTheDocument();
  });

  it('saves the profile and moves on to paying', async () => {
    let saved: Record<string, unknown> | null = null;
    server.use(
      signedInAs(makeUser({ profile_complete: false, membership: NONE })),
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
      signedInAs(makeUser({ profile_complete: false, membership: NONE })),
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile({ phone: '' }))),
    );

    renderWizard('/join');

    await screen.findByRole('heading', { name: 'About you' });
    await userEvent.click(await screen.findByRole('button', { name: 'Save and continue' }));

    expect(await screen.findByText('A phone number is required.')).toBeInTheDocument();
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
    let user = makeUser({ profile_complete: true, membership: NONE });
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

  it('offers a way back to paying when the payment was declined', async () => {
    server.use(
      signedInAs(makeUser({ profile_complete: true, membership: NONE })),
      http.get(`${API}/me/membership`, () => HttpResponse.json(CURRENT_DETAIL)),
      http.get(`${API}/site/config`, () => HttpResponse.json(SITE_CONFIG)),
      http.post(`${API}/payments/stripe/confirm`, () =>
        HttpResponse.json({ detail: 'Not confirmed' }, { status: 400 }),
      ),
      http.get(`${API}/payments/42`, () =>
        HttpResponse.json({ status: 'failed', membership: NONE }),
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
  const FRIEND: MembershipStatus = { ...NONE, status: 'friend' };
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

  it('names the kind on the verify step', async () => {
    stubFriendApi(makeFriend({ email_verified: false, profile_complete: false }));
    renderWizard('/join');

    await screen.findByRole('heading', { name: 'Check your email' });
    expect(screen.getByText('Step 2 of 5 · Joining as a friend')).toBeInTheDocument();
  });

  it('names a member on the verify step too', async () => {
    stubApi(makeUser({ email_verified: false, profile_complete: false, membership: NONE }));
    renderWizard('/join');

    await screen.findByRole('heading', { name: 'Check your email' });
    expect(screen.getByText('Step 2 of 5 · Joining as a member')).toBeInTheDocument();
  });

  it('asks a friend for a contribution on the way through from the profile', async () => {
    stubFriendApi(makeFriend({ profile_complete: false }));
    server.use(http.put(`${API}/me/profile`, () => HttpResponse.json(makeProfile())));
    renderWizard('/join');

    await screen.findByRole('heading', { name: 'About you' });
    await userEvent.click(await screen.findByRole('button', { name: 'Save and continue' }));

    expect(
      await screen.findByRole('heading', { name: 'Contribute to CalDART' }),
    ).toBeInTheDocument();
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
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }));

    expect(await screen.findByRole('heading', { name: 'Welcome to CalDART' })).toBeInTheDocument();
    expect(path()).toBe('/join/done');
  });

  it('promises no receipt to a friend who gave nothing', async () => {
    stubFriendApi(makeFriend({ profile_complete: false }));
    server.use(http.put(`${API}/me/profile`, () => HttpResponse.json(makeProfile())));
    renderWizard('/join');

    await userEvent.click(await screen.findByRole('button', { name: 'Save and continue' }));
    await screen.findByRole('radio', { name: /Participating/ });
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }));

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

    expect(
      await screen.findByText('You are a friend of the California DART Network.'),
    ).toBeInTheDocument();
  });
});
