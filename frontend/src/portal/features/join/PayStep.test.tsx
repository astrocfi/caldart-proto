import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, delay, http } from 'msw';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import type { MembershipStatus, PaymentsConfig, PersonKind } from '@/portal/api/types';
import { AUTH_ME_KEY } from '@/portal/auth/useAuth';
import { API, makeUser, signedInAs } from '@test/handlers';
import { makeTestQueryClient, renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { PayStep } from './PayStep';

const FRIEND_LINK = 'Join as a friend instead (no dues)';
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
  const { container } = renderWithProviders(
    <Harness initial={initial} onPaid={handlePaid} onDone={handleDone} />,
    { client },
  );
  return { handlePaid, handleDone, container };
}

/** Turn a member's checkout into a friend's donation and continue without a gift. */
async function continueAsFriend(): Promise<void> {
  await userEvent.click(await screen.findByRole('button', { name: FRIEND_LINK }));
  await screen.findByRole('radio', { name: /Participating/ });
  await userEvent.click(screen.getByRole('button', { name: 'Continue without a gift' }));
}

describe('<PayStep/>', () => {
  it('holds the checkout in the step’s own card, with one heading and no eyebrow', async () => {
    stubPayApi('member');
    const { container } = renderPayStep('member');

    await screen.findByText('$45.00', { selector: '.plan-card__price' });
    expect(container.querySelectorAll('.card')).toHaveLength(1);
    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual([
      'Pay your dues',
    ]);
    expect(container.querySelector('.card > .eyebrow')).toBeNull();
  });
});

describe('<PayStep/> for a member who chooses to be a friend', () => {
  it('turns the step into a friend’s donation', async () => {
    stubPayApi('member');
    renderPayStep('member');

    await userEvent.click(await screen.findByRole('button', { name: FRIEND_LINK }));

    expect(screen.getByRole('heading', { name: 'Donate to CalDART' })).toBeInTheDocument();
    expect(screen.getByTestId('kind')).toHaveTextContent('friend');
  });

  it('makes the account a friend as it moves on without a gift', async () => {
    const kindCalls = stubPayApi('member');
    const { handleDone, handlePaid } = renderPayStep('member');

    await continueAsFriend();

    await waitFor(() => expect(handleDone).toHaveBeenCalledOnce());
    expect(handlePaid).not.toHaveBeenCalled();
    expect(kindCalls).toEqual(['POST']);
  });

  it('makes the account a friend once the donation is paid', async () => {
    const kindCalls = stubPayApi('member');
    const { handleDone, handlePaid } = renderPayStep('member');

    await userEvent.click(await screen.findByRole('button', { name: FRIEND_LINK }));
    await userEvent.click(await screen.findByRole('radio', { name: /Participating/ }));
    await userEvent.click(await screen.findByRole('button', { name: 'Succeed' }));

    await waitFor(() => expect(handleDone).toHaveBeenCalledOnce());
    expect(handlePaid).toHaveBeenCalledOnce();
    expect(kindCalls).toEqual(['POST']);
  });
});

describe('<PayStep/> when making the account a friend', () => {
  it('waits on its button, so a second press sends nothing more', async () => {
    const kindCalls = stubPayApi('member');
    server.use(
      http.post(`${API}/me/kind/friend`, async () => {
        kindCalls.push('POST');
        await delay(200);
        return HttpResponse.json(makeUser({ kind: 'friend', membership: UNPAID }));
      }),
    );
    const { handleDone } = renderPayStep('member');

    await userEvent.click(await screen.findByRole('button', { name: FRIEND_LINK }));
    await screen.findByRole('radio', { name: /Participating/ });
    const skip = screen.getByRole('button', { name: 'Continue without a gift' });
    await userEvent.click(skip);

    expect(skip).toBeDisabled();
    await waitFor(() => expect(handleDone).toHaveBeenCalledOnce());
    expect(kindCalls).toEqual(['POST']);
  });

  it('says in its own words when the change is refused, never the server’s', async () => {
    stubPayApi('member');
    server.use(
      http.post(`${API}/me/kind/friend`, () =>
        HttpResponse.json({ keep_contribution: ['This field is required.'] }, { status: 400 }),
      ),
    );
    renderPayStep('member');

    await userEvent.click(await screen.findByRole('button', { name: FRIEND_LINK }));
    await screen.findByRole('radio', { name: /Participating/ });
    await userEvent.click(screen.getByRole('button', { name: 'Continue without a gift' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Your account could not be changed to a friend. Try again, or contact CalDART.',
    );
    expect(screen.queryByText('This field is required.')).not.toBeInTheDocument();
  });
});

describe('<PayStep/> for a friend', () => {
  it('moves on without a gift and without asking the server to change anything', async () => {
    const kindCalls = stubPayApi('friend');
    const { handleDone } = renderPayStep('friend');

    await screen.findByRole('radio', { name: /Participating/ });
    await userEvent.click(screen.getByRole('button', { name: 'Continue without a gift' }));

    await waitFor(() => expect(handleDone).toHaveBeenCalledOnce());
    expect(kindCalls).toEqual([]);
  });
});

describe('<PayStep/> for a friend who chooses to be a member', () => {
  it('offers a way back to membership under the donation', async () => {
    stubPayApi('friend');
    renderPayStep('friend');

    await screen.findByRole('radio', { name: /Participating/ });
    expect(screen.getByRole('button', { name: MEMBER_BUTTON })).toBeInTheDocument();
  });

  it('swaps the donation for the dues checkout', async () => {
    stubPayApi('friend');
    renderPayStep('friend');

    await userEvent.click(await screen.findByRole('button', { name: MEMBER_BUTTON }));

    expect(screen.getByRole('heading', { name: 'Pay your dues' })).toBeInTheDocument();
    expect(await screen.findByTestId('checkout-total')).toHaveTextContent('$45.00');
  });

  it('changes nothing on the server until the dues are paid', async () => {
    const kindCalls = stubPayApi('friend');
    renderPayStep('friend');

    await userEvent.click(await screen.findByRole('button', { name: MEMBER_BUTTON }));
    await screen.findByTestId('checkout-total');

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
    const { handleDone } = renderPayStep('friend');

    await userEvent.click(await screen.findByRole('button', { name: MEMBER_BUTTON }));
    await continueAsFriend();

    await waitFor(() => expect(handleDone).toHaveBeenCalledOnce());
    expect(kindCalls).toEqual([]);
  });
});
