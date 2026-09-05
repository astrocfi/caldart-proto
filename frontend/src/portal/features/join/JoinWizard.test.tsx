import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { API, makeUser, signedInAs } from '../../../test/handlers';
import { renderWithProviders } from '../../../test/render';
import { server } from '../../../test/server';
import type { MembershipDetail, MembershipStatus, SiteConfig, User } from '../../api/types';
import { TEST_DARTS, makeProfile } from '../profile/fixtures';
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

const CURRENT_DETAIL: MembershipDetail = { ...CURRENT, history: [] };

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

/** Everything the wizard's four steps might ask for. */
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
  );
}

describe('<JoinWizard/> resume logic', () => {
  it('starts a visitor with no account on step 1', async () => {
    stubApi(null);
    renderWizard('/join');

    expect(await screen.findByRole('heading', { name: 'Create your account' })).toBeInTheDocument();
    expect(path()).toBe('/join/account');
  });

  it('resumes a signed-in member with a thin profile on step 2', async () => {
    stubApi(makeUser({ profile_complete: false, membership: NONE }));
    renderWizard('/join');

    expect(await screen.findByRole('heading', { name: 'About you' })).toBeInTheDocument();
    expect(path()).toBe('/join/profile');
  });

  it('resumes a complete profile without a membership on step 3', async () => {
    stubApi(makeUser({ profile_complete: true, membership: NONE }));
    renderWizard('/join');

    expect(await screen.findByRole('heading', { name: 'Pay your dues' })).toBeInTheDocument();
    expect(path()).toBe('/join/pay');
  });

  it('resumes a paid-up member on step 4', async () => {
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

describe('<JoinWizard/> progress', () => {
  beforeEach(() => stubApi(null));

  it('marks the current step and leaves the rest to do', async () => {
    renderWizard('/join/account');

    const steps = await screen.findByRole('list', { name: 'Join progress' });
    const [account, profile] = Array.from(steps.querySelectorAll('li'));
    expect(account).toHaveAttribute('data-state', 'current');
    expect(account).toHaveAttribute('aria-current', 'step');
    expect(profile).toHaveAttribute('data-state', 'todo');
  });

  it('names all four steps', async () => {
    renderWizard('/join/account');

    const steps = await screen.findByRole('list', { name: 'Join progress' });
    expect(Array.from(steps.querySelectorAll('li')).map((li) => li.textContent)).toEqual([
      'Account',
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
    );
  });

  it('registers an account and moves on to the profile step', async () => {
    let registered: unknown = null;
    let user: User | null = null;
    server.use(
      http.get(`${API}/auth/me`, () =>
        user ? HttpResponse.json(user) : HttpResponse.json({ detail: 'no' }, { status: 401 }),
      ),
      http.get(`${API}/me/profile`, () => HttpResponse.json(makeProfile({ phone: '' }))),
      http.post(`${API}/auth/register`, async ({ request }) => {
        registered = await request.json();
        user = makeUser({ profile_complete: false, membership: NONE });
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

    expect(await screen.findByRole('heading', { name: 'About you' })).toBeInTheDocument();
    expect(path()).toBe('/join/profile');
    expect(registered).toEqual({
      first_name: 'Marta',
      last_name: 'Reyes',
      email: 'marta@example.org',
      password: 'a-good-password',
    });
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
});
