import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import type { MemberDetail, MembershipStatus, RenewalMandate } from '@/portal/api/types';
import { makeLedger, makeMandate } from '@test/fixtures/finance';
import { LIFETIME, makeDetail } from '@test/fixtures/members';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { MemberAccountActions } from './MemberAccountActions';

const MEMBER = makeDetail();
const FRIEND: MembershipStatus = {
  status: 'friend',
  expires_on: null,
  plan: null,
  is_lifetime: false,
};

/** The bodies posted to each action, by action. */
let posted: Record<string, unknown[]>;

function stub({
  mandate = null,
  answer,
}: {
  mandate?: RenewalMandate | null;
  answer?: (action: string, body: unknown) => Response;
} = {}) {
  server.use(
    http.get(`${API}/admin/payments/ledger/${MEMBER.id}`, () =>
      HttpResponse.json(makeLedger({ mandate })),
    ),
    http.post(`${API}/admin/members/${MEMBER.id}/:action`, async ({ params, request }) => {
      const action = String(params.action);
      const text = await request.text();
      const body: unknown = text === '' ? null : JSON.parse(text);
      (posted[action] ??= []).push(body);
      return answer?.(action, body) ?? HttpResponse.json(MEMBER);
    }),
  );
}

function renderActions(member: MemberDetail = MEMBER) {
  return renderWithProviders(<MemberAccountActions member={member} />);
}

describe('MemberAccountActions', () => {
  beforeEach(() => {
    posted = {};
  });

  it('offers a member both making a friend and deactivating', async () => {
    stub();
    renderActions();

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Make a friend' })).toBeEnabled(),
    );
    expect(screen.getByRole('button', { name: 'Deactivate account' })).toBeInTheDocument();
  });

  it('offers a friend no switch to friend', () => {
    stub();
    renderActions(makeDetail({ kind: 'friend', membership: FRIEND }));

    expect(screen.queryByRole('button', { name: 'Make a friend' })).not.toBeInTheDocument();
  });

  it('offers a life member no switch to friend', () => {
    stub();
    renderActions(makeDetail({ membership: LIFETIME }));

    expect(screen.queryByRole('button', { name: 'Make a friend' })).not.toBeInTheDocument();
  });

  it('shows the day a pending change takes effect instead of the button', () => {
    stub();
    renderActions(makeDetail({ friend_on: '2027-07-01' }));

    expect(screen.getByText('Ana Bracco becomes a friend of CalDART on 07/01/2027.')).toBeVisible();
  });

  it('shows a donor no account actions', () => {
    stub();
    renderActions(makeDetail({ kind: 'donor' }));

    expect(screen.queryByRole('heading', { name: 'Account' })).not.toBeInTheDocument();
  });

  it('makes a friend once confirmed', async () => {
    stub();
    renderActions();

    await userEvent.click(await screen.findByRole('button', { name: 'Make a friend' }));
    expect(screen.getByText(/membership stays current through 06\/30\/2027/)).toBeVisible();
    await userEvent.click(
      within(screen.getByRole('region', { name: 'Make a friend' })).getByRole('button', {
        name: 'Yes, make a friend',
      }),
    );

    await waitFor(() => expect(posted.friend).toEqual([{}]));
  });

  it('opens Make a friend on Cancel, so a second Enter converts nobody', async () => {
    stub({ mandate: makeMandate({ contribution_cents: 2_500 }) });
    renderActions();

    await userEvent.click(await screen.findByRole('button', { name: 'Make a friend' }));

    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
  });

  it('asks about a renewal contribution and sends the answer', async () => {
    stub({ mandate: makeMandate({ contribution_cents: 2_500 }) });
    renderActions();

    await userEvent.click(await screen.findByRole('button', { name: 'Make a friend' }));
    expect(screen.getByText(/also gives \$25 each year/)).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Keep the contribution' }));

    await waitFor(() => expect(posted.friend).toEqual([{ keep_contribution: true }]));
  });

  it('asks about a contribution the server says needs an answer', async () => {
    stub({
      answer: (_action, body) =>
        body !== null && typeof body === 'object' && 'keep_contribution' in body
          ? HttpResponse.json(MEMBER)
          : HttpResponse.json({ keep_contribution: ['This field is required.'] }, { status: 400 }),
    });
    renderActions();

    await userEvent.click(await screen.findByRole('button', { name: 'Make a friend' }));
    await userEvent.click(
      within(screen.getByRole('region', { name: 'Make a friend' })).getByRole('button', {
        name: 'Yes, make a friend',
      }),
    );

    expect(await screen.findByRole('button', { name: 'Stop it' })).toBeInTheDocument();
    expect(screen.queryByText('This field is required.')).not.toBeInTheDocument();
  });

  it('draws a refusal of the switch', async () => {
    stub({
      mandate: makeMandate({ contribution_cents: 2_500 }),
      answer: () =>
        HttpResponse.json(
          {
            keep_contribution: [
              'They already have a recurring donation, so the contribution cannot be kept as one.',
            ],
          },
          { status: 400 },
        ),
    });
    renderActions();

    await userEvent.click(await screen.findByRole('button', { name: 'Make a friend' }));
    await userEvent.click(screen.getByRole('button', { name: 'Keep the contribution' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'They already have a recurring donation, so the contribution cannot be kept as one.',
    );
  });

  it('deactivates once confirmed', async () => {
    stub();
    renderActions();

    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));
    await userEvent.click(
      within(screen.getByRole('region', { name: 'Deactivate account' })).getByRole('button', {
        name: 'Yes, deactivate account',
      }),
    );

    await waitFor(() => expect(posted.deactivate).toHaveLength(1));
  });

  it('draws a refused deactivation', async () => {
    stub({
      answer: () =>
        HttpResponse.json(
          {
            detail:
              'You cannot activate or deactivate an account that holds roles you do not hold.',
          },
          { status: 400 },
        ),
    });
    renderActions();

    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));
    await userEvent.click(
      within(screen.getByRole('region', { name: 'Deactivate account' })).getByRole('button', {
        name: 'Yes, deactivate account',
      }),
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'You cannot activate or deactivate an account that holds roles you do not hold.',
    );
  });

  it('offers a deactivated account reactivation instead', () => {
    stub();
    renderActions(makeDetail({ is_active: false }));

    expect(screen.getByRole('button', { name: 'Reactivate account' })).toBeInTheDocument();
  });

  it('reactivates once confirmed', async () => {
    stub();
    renderActions(makeDetail({ is_active: false }));

    await userEvent.click(screen.getByRole('button', { name: 'Reactivate account' }));
    await userEvent.click(
      within(screen.getByRole('region', { name: 'Reactivate account' })).getByRole('button', {
        name: 'Yes, reactivate account',
      }),
    );

    await waitFor(() => expect(posted.reactivate).toHaveLength(1));
  });

  it('says when a user administrator has blocked reactivation', () => {
    stub();
    renderActions(makeDetail({ is_active: false, reactivation_blocked: true }));

    expect(screen.getByText(/blocked it from reactivating/)).toBeVisible();
  });
});
