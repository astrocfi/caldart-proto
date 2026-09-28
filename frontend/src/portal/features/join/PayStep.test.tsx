import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import type { MembershipStatus, PaymentsConfig, PersonKind } from '@/portal/api/types';
import { AUTH_ME_KEY } from '@/portal/auth/useAuth';
import { API, makeUser, signedInAs } from '@test/handlers';
import { makeTestQueryClient, renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { PayStep } from './PayStep';

const FRIEND_CARD = /I changed my mind, I just want to be a friend/;
const MEMBER_BUTTON = 'I changed my mind, I want to be a member';

/** What a joiner who has not paid reads as, whichever kind they chose: a friend. */
const UNPAID: MembershipStatus = {
  status: 'friend',
  expires_on: null,
  plan: null,
  is_lifetime: false,
};

const CURRENT: MembershipStatus = {
  status: 'current',
  expires_on: '2027-06-30',
  plan: 'Annual',
  is_lifetime: false,
};

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
  contribution_tiers: [
    { label: 'No contribution', cents: 0 },
    { label: 'Participating', cents: 2000 },
  ],
  max_contribution_cents: 9_999_900,
};

/**
 * Serve the pay step's endpoints for an unpaid joiner of `kind`, recording every
 * request that would change the account's kind.
 */
function stubPayApi(kind: PersonKind): string[] {
  const kindCalls: string[] = [];
  server.use(
    signedInAs(makeUser({ kind, membership: UNPAID })),
    http.get(`${API}/payments/config`, () => HttpResponse.json(PAYMENTS_CONFIG)),
    http.all(`${API}/me/kind/friend`, ({ request }) => {
      kindCalls.push(request.method);
      return HttpResponse.json(makeUser({ kind: 'friend', membership: UNPAID }));
    }),
    http.post(`${API}/payments/checkout`, () =>
      HttpResponse.json({ payment_id: 5, provider: 'mock', client: {} }, { status: 201 }),
    ),
    http.post(`${API}/payments/mock/complete`, () =>
      HttpResponse.json({ status: 'succeeded', membership: CURRENT }),
    ),
  );
  return kindCalls;
}

interface HarnessProps {
  initial: PersonKind;
  onPaid: () => void;
  onDone: () => void;
}

/** Holds the kind the step is showing, as the wizard does. */
function Harness({ initial, onPaid: handlePaid, onDone: handleDone }: HarnessProps) {
  const [kind, setKind] = useState<PersonKind>(initial);
  return (
    <>
      <span data-testid="kind">{kind}</span>
      <PayStep
        joiningAs={kind}
        onJoiningAsChange={(next) => setKind(next)}
        onPaid={handlePaid}
        onDone={handleDone}
      />
    </>
  );
}

/** Render the step for a signed-in, unpaid joiner who chose `initial` at sign-up. */
function renderPayStep(initial: PersonKind) {
  const handlePaid = vi.fn();
  const handleDone = vi.fn();
  const client = makeTestQueryClient();
  client.setQueryData(AUTH_ME_KEY, makeUser({ kind: initial, membership: UNPAID }));
  renderWithProviders(<Harness initial={initial} onPaid={handlePaid} onDone={handleDone} />, {
    client,
  });
  return { handlePaid, handleDone };
}

/** Choose the friend card on a member's checkout and continue as a friend. */
async function continueAsFriend(): Promise<void> {
  await userEvent.click(await screen.findByRole('radio', { name: FRIEND_CARD }));
  await userEvent.click(screen.getByRole('button', { name: 'Continue as a friend' }));
}

describe('<PayStep/> for a member who chooses to be a friend', () => {
  it('offers a friend’s contribution instead of moving on', async () => {
    stubPayApi('member');
    const { handleDone } = renderPayStep('member');

    await continueAsFriend();

    expect(
      await screen.findByRole('heading', { name: 'Contribute to CalDART' }),
    ).toBeInTheDocument();
    expect(handleDone).not.toHaveBeenCalled();
  });

  it('offers Not now on the contribution', async () => {
    stubPayApi('member');
    renderPayStep('member');

    await continueAsFriend();

    expect(await screen.findByRole('button', { name: 'Not now' })).toBeInTheDocument();
  });

  it('tells the wizard the joiner is a friend now', async () => {
    stubPayApi('member');
    renderPayStep('member');

    await continueAsFriend();

    await waitFor(() => expect(screen.getByTestId('kind')).toHaveTextContent('friend'));
  });

  it('moves on when the friend says Not now', async () => {
    stubPayApi('member');
    const { handleDone, handlePaid } = renderPayStep('member');

    await continueAsFriend();
    await screen.findByRole('radio', { name: /Participating/ });
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }));

    expect(handleDone).toHaveBeenCalledOnce();
    expect(handlePaid).not.toHaveBeenCalled();
  });
});

describe('<PayStep/> for a friend who chooses to be a member', () => {
  it('offers a way back to membership under the contribution', async () => {
    stubPayApi('friend');
    renderPayStep('friend');

    await screen.findByRole('radio', { name: /Participating/ });
    expect(screen.getByRole('button', { name: MEMBER_BUTTON })).toBeInTheDocument();
  });

  it('swaps the contribution for the dues checkout', async () => {
    stubPayApi('friend');
    renderPayStep('friend');

    await userEvent.click(await screen.findByRole('button', { name: MEMBER_BUTTON }));

    expect(screen.getByRole('heading', { name: 'Pay your dues' })).toBeInTheDocument();
    expect(await screen.findByRole('radio', { name: /Annual/ })).toBeChecked();
  });

  it('changes nothing on the server until the dues are paid', async () => {
    const kindCalls = stubPayApi('friend');
    renderPayStep('friend');

    await userEvent.click(await screen.findByRole('button', { name: MEMBER_BUTTON }));
    await screen.findByRole('radio', { name: /Annual/ });

    expect(kindCalls).toEqual([]);
  });

  it('moves on once the dues are paid', async () => {
    stubPayApi('friend');
    const { handleDone, handlePaid } = renderPayStep('friend');

    await userEvent.click(await screen.findByRole('button', { name: MEMBER_BUTTON }));
    await userEvent.click(await screen.findByRole('button', { name: 'Succeed' }));

    await waitFor(() => expect(handleDone).toHaveBeenCalledOnce());
    expect(handlePaid).toHaveBeenCalledOnce();
  });

  it('goes back to being a friend without asking the server again', async () => {
    const kindCalls = stubPayApi('friend');
    renderPayStep('friend');

    await userEvent.click(await screen.findByRole('button', { name: MEMBER_BUTTON }));
    await continueAsFriend();

    expect(
      await screen.findByRole('heading', { name: 'Contribute to CalDART' }),
    ).toBeInTheDocument();
    expect(kindCalls).toEqual([]);
  });
});
