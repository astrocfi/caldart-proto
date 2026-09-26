import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import {
  API,
  CURRENT_MEMBERSHIP,
  LIFETIME_MEMBERSHIP,
  kindSwitchHandlers,
  makeUser,
  signedInAs,
} from '@test/handlers';
import type { KindSwitchCalls } from '@test/handlers';
import { makeMandate } from '@test/fixtures/payments';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { MembershipStatus, RenewalMandate, User } from '@/portal/api/types';
import { KindCard, KindSwitch, kindState } from './KindSwitch';

const FRIEND_MEMBERSHIP: MembershipStatus = {
  status: 'friend',
  expires_on: null,
  plan: null,
  is_lifetime: false,
};

/** A member whose membership ran out: nothing is current, and they are still a member. */
const EXPIRED_MEMBERSHIP: MembershipStatus = {
  status: 'expired',
  expires_on: '2025-06-30',
  plan: 'Annual',
  is_lifetime: false,
};

interface Setup {
  user?: User;
  renewal?: RenewalMandate | null;
  /** What `POST /me/kind/friend` answers. */
  become?: User;
}

/** Signs `user` in, answers the renewal read, and records the kind calls. */
function setUp({ user = makeUser(), renewal = null, become }: Setup = {}): KindSwitchCalls {
  const calls: KindSwitchCalls = { bodies: [], undos: 0 };
  server.use(
    signedInAs(user),
    http.get(`${API}/me/renewal`, () => HttpResponse.json({ mandate: renewal })),
    ...kindSwitchHandlers({
      become: become ?? makeUser({ friend_on: '2027-07-01' }),
      undo: makeUser(),
      calls,
    }),
  );
  return calls;
}

async function openPanel() {
  await userEvent.click(await screen.findByRole('button', { name: 'Make me a friend' }));
}

/** The panel's button called `name`, once the renewal has loaded and enabled it. */
async function readyButton(name: string): Promise<HTMLElement> {
  const button = await screen.findByRole('button', { name });
  await waitFor(() => expect(button).toBeEnabled());
  return button;
}

describe('kindState', () => {
  it('reads a friend from the membership state', () => {
    expect(kindState(makeUser({ kind: 'friend' }), FRIEND_MEMBERSHIP)).toEqual({ kind: 'friend' });
  });

  it('reads a current life member as lifetime', () => {
    expect(kindState(makeUser(), LIFETIME_MEMBERSHIP)).toEqual({ kind: 'lifetime' });
  });

  it('reads a pending change from friend_on', () => {
    expect(kindState(makeUser({ friend_on: '2027-07-01' }), CURRENT_MEMBERSHIP)).toEqual({
      kind: 'pending',
      friendOn: '2027-07-01',
    });
  });

  it('gives a current member the end of their membership', () => {
    expect(kindState(makeUser(), CURRENT_MEMBERSHIP)).toEqual({
      kind: 'member',
      expiresOn: '2027-06-30',
    });
  });

  it('gives a member with nothing current no end date', () => {
    expect(kindState(makeUser(), EXPIRED_MEMBERSHIP)).toEqual({ kind: 'member', expiresOn: null });
  });
});

describe('<KindSwitch/>', () => {
  it('offers a member Make me a friend', async () => {
    setUp();
    renderWithProviders(<KindSwitch />);
    expect(await screen.findByRole('button', { name: 'Make me a friend' })).toBeInTheDocument();
  });

  it('says when a current member becomes a friend', async () => {
    setUp();
    renderWithProviders(<KindSwitch />);
    await openPanel();
    expect(
      screen.getByText(
        'Your membership stays current through 2027/06/30. On 2027/07/01 you become a friend ' +
          'of CalDART: no dues, no expiry, and no renewal reminders.',
      ),
    ).toBeInTheDocument();
  });

  it('says a member with nothing current becomes a friend today', async () => {
    setUp({ user: makeUser({ membership: EXPIRED_MEMBERSHIP }) });
    renderWithProviders(<KindSwitch />);
    await openPanel();
    expect(
      screen.getByText(
        'You become a friend of CalDART today: no dues, no expiry, and no renewal reminders.',
      ),
    ).toBeInTheDocument();
  });

  it('confirms with an empty body when the renewal gives no contribution', async () => {
    const calls = setUp({ renewal: makeMandate({ contribution_cents: 0, kind: 'renewal' }) });
    renderWithProviders(<KindSwitch />);
    await openPanel();
    await userEvent.click(await readyButton('Make me a friend'));
    await screen.findByText('You become a friend on 2027/07/01.');
    expect(calls.bodies).toEqual([{}]);
  });

  it('waits for the renewal before the panel can confirm', async () => {
    setUp();
    server.use(http.get(`${API}/me/renewal`, () => new Promise<never>(() => undefined)));
    renderWithProviders(<KindSwitch />);
    await openPanel();
    expect(screen.getByRole('button', { name: 'Make me a friend' })).toBeDisabled();
  });

  it('asks whether to keep a contribution the renewal gives', async () => {
    setUp({ renewal: makeMandate({ contribution_cents: 2500 }) });
    renderWithProviders(<KindSwitch />);
    await openPanel();
    expect(
      await screen.findByText(
        'Your automatic renewal also gives $25 each year. Keep giving $25 a year as a ' +
          'recurring donation?',
      ),
    ).toBeInTheDocument();
  });

  it('keeps the contribution when asked to', async () => {
    const calls = setUp({ renewal: makeMandate({ contribution_cents: 2500 }) });
    renderWithProviders(<KindSwitch />);
    await openPanel();
    await userEvent.click(await readyButton('Keep the contribution'));
    await screen.findByText('You become a friend on 2027/07/01.');
    expect(calls.bodies).toEqual([{ keep_contribution: true }]);
  });

  it('stops the contribution when asked to', async () => {
    const calls = setUp({ renewal: makeMandate({ contribution_cents: 2500 }) });
    renderWithProviders(<KindSwitch />);
    await openPanel();
    await userEvent.click(await readyButton('Stop it'));
    await screen.findByText('You become a friend on 2027/07/01.');
    expect(calls.bodies).toEqual([{ keep_contribution: false }]);
  });

  it.each(['canceled', 'paused'] as const)(
    'asks nothing about a contribution on a %s renewal',
    async (status) => {
      const calls = setUp({ renewal: makeMandate({ contribution_cents: 2500, status }) });
      renderWithProviders(<KindSwitch />);
      await openPanel();
      await userEvent.click(await readyButton('Make me a friend'));
      await screen.findByText('You become a friend on 2027/07/01.');
      expect(calls.bodies).toEqual([{}]);
    },
  );

  it('closes the panel on Cancel without asking the server', async () => {
    const calls = setUp();
    renderWithProviders(<KindSwitch />);
    await openPanel();
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(calls.bodies).toEqual([]);
  });

  it('shows the server refusal', async () => {
    setUp();
    server.use(
      http.post(`${API}/me/kind/friend`, () =>
        HttpResponse.json({ detail: 'A lifetime member stays a member.' }, { status: 400 }),
      ),
    );
    renderWithProviders(<KindSwitch />);
    await openPanel();
    await userEvent.click(await readyButton('Make me a friend'));
    expect(await screen.findByRole('alert')).toHaveTextContent('A lifetime member stays a member.');
  });

  it('shows a pending change with its day', async () => {
    setUp({ user: makeUser({ friend_on: '2027-07-01' }) });
    renderWithProviders(<KindSwitch />);
    expect(await screen.findByText('You become a friend on 2027/07/01.')).toBeInTheDocument();
  });

  it('undoes a pending change', async () => {
    const calls = setUp({ user: makeUser({ friend_on: '2027-07-01' }) });
    renderWithProviders(<KindSwitch />);
    await userEvent.click(await screen.findByRole('button', { name: 'Undo' }));
    await screen.findByRole('button', { name: 'Make me a friend' });
    expect(calls.undos).toBe(1);
  });

  it('sends a friend to become a member', async () => {
    setUp({ user: makeUser({ kind: 'friend', membership: FRIEND_MEMBERSHIP }) });
    renderWithProviders(<KindSwitch />);
    expect(await screen.findByRole('link', { name: 'Make me a member' })).toHaveAttribute(
      'href',
      '/membership/join',
    );
  });

  it('offers a life member nothing', async () => {
    setUp({ user: makeUser({ membership: LIFETIME_MEMBERSHIP }) });
    renderWithProviders(<KindCard />);
    await screen.findByText('You are a life member of CalDART.');
    expect(screen.queryByRole('button', { name: 'Make me a friend' })).toBeNull();
  });
});

describe('<KindCard/>', () => {
  it('tells a friend what they are', async () => {
    setUp({ user: makeUser({ kind: 'friend', membership: FRIEND_MEMBERSHIP }) });
    renderWithProviders(<KindCard />);
    expect(
      await screen.findByText(
        'You are a friend of CalDART: no dues, no expiry. Become a member any time.',
      ),
    ).toBeInTheDocument();
  });

  it('tells a member what they are', async () => {
    setUp();
    renderWithProviders(<KindCard />);
    expect(await screen.findByText('You are a member of CalDART.')).toBeInTheDocument();
  });

  it('is headed Your kind of account', async () => {
    setUp();
    renderWithProviders(<KindCard />);
    expect(
      await screen.findByRole('heading', { name: 'Your kind of account' }),
    ).toBeInTheDocument();
  });
});
