import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { QueryClient } from '@tanstack/react-query';
import { HttpResponse, http } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import type { AccountChange, AdminUserDetail, User } from '@/portal/api/types';
import { formatDateTime } from '@/portal/components/DateText';
import { API, makeAdminUserDetail, makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders, signedInClient } from '@test/render';
import { server } from '@test/server';
import { UserDetailPage } from './UserDetailPage';

const ROLES = [
  { slug: 'member', description: 'Own profile, own payments and membership.' },
  { slug: 'dart_leader', description: 'Look up any member before a flight.' },
  { slug: 'system_admin', description: 'Everything, plus backups and health.' },
];

const TARGET = makeAdminUserDetail({
  id: 7,
  email: 'priya@example.org',
  first_name: 'Priya',
  last_name: 'Raman',
  roles: ['member'],
});

/** `TARGET` with an address the bounce check found bouncing at noon UTC, October 1st. */
const BOUNCED = makeAdminUserDetail({
  ...TARGET,
  email_bounced_at: '2026-10-01T12:00:00Z',
  email_bounce_detail: '5.1.1 550 User unknown',
});

interface StubOptions {
  target?: AdminUserDetail;
  me?: User;
  patch?: Parameters<typeof http.patch>[1];
  history?: AccountChange[];
}

function stubDetail({ target = TARGET, me, patch, history = [] }: StubOptions = {}) {
  const patched: unknown[] = [];
  server.use(
    signedInAs(me ?? makeUser({ id: 1, roles: ['member', 'user_admin'] })),
    http.get(`${API}/roles`, () => HttpResponse.json(ROLES)),
    http.get(`${API}/admin/users/${target.id}/history`, () => HttpResponse.json(history)),
    http.get(`${API}/admin/users/${target.id}`, () => HttpResponse.json(target)),
    http.patch(
      `${API}/admin/users/${target.id}`,
      patch ??
        (async ({ request }) => {
          const body = (await request.json()) as Record<string, unknown>;
          patched.push(body);
          return HttpResponse.json({ ...target, ...body });
        }),
    ),
  );
  return patched;
}

/** The value the Account card shows beside the label `term`. */
function shown(term: string): string | null {
  const label = screen.getAllByRole('term').find((dt) => dt.textContent === term);
  return label?.nextElementSibling?.textContent ?? null;
}

function renderDetail(id = String(TARGET.id), client?: QueryClient) {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/users/:id" element={<UserDetailPage />} />
    </Routes>,
    { route: `/admin/users/${id}`, client },
  );
}

describe('UserDetailPage', () => {
  it('links the member record for a user administrator who is an account administrator', async () => {
    const client = signedInClient('user_admin', 'account_admin');
    stubDetail({ me: makeUser({ id: 1, roles: ['member', 'user_admin', 'account_admin'] }) });
    renderDetail(String(TARGET.id), client);

    expect(await screen.findByRole('link', { name: 'Member record' })).toHaveAttribute(
      'href',
      '/admin/members/7',
    );
  });

  it('offers a user administrator alone no link to the member record', async () => {
    const client = signedInClient('user_admin');
    stubDetail();
    renderDetail(String(TARGET.id), client);

    await screen.findByRole('heading', { name: 'Priya Raman' });

    expect(screen.queryByRole('link', { name: 'Member record' })).not.toBeInTheDocument();
  });

  it('shows the account and every role with its description', async () => {
    stubDetail();
    renderDetail();

    expect(await screen.findByRole('heading', { name: 'Priya Raman' })).toBeInTheDocument();
    expect(screen.getByText('Look up any member before a flight.')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /member/i })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: /dart leader/i })).not.toBeChecked();
  });

  it('names each role in words rather than by its slug', async () => {
    stubDetail();
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    expect(screen.getByRole('checkbox', { name: 'System administrator' })).toBeInTheDocument();
  });

  it('saves a role toggle', async () => {
    const patched = stubDetail();
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    await userEvent.click(screen.getByRole('checkbox', { name: /dart leader/i }));
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => expect(patched).toHaveLength(1));
    expect(patched[0]).toMatchObject({ roles: ['member', 'dart_leader'] });
    expect(await screen.findByText(/account saved/i)).toBeInTheDocument();
  });

  it.each([
    ['First name', 'Priya'],
    ['Last name', 'Raman'],
  ])('shows the %s as text', async (term, value) => {
    stubDetail();
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    expect(shown(term)).toBe(value);
  });

  it('shows the email address as text, with whether it is verified', async () => {
    stubDetail();
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    expect(shown('Email address')).toMatch(/^priya@example\.org Verified/);
  });

  it.each(['First name', 'Last name', 'Email address'])(
    'offers no box to change the %s',
    async (name) => {
      stubDetail();
      renderDetail();
      await screen.findByRole('heading', { name: 'Priya Raman' });

      expect(screen.queryByRole('textbox', { name })).not.toBeInTheDocument();
    },
  );

  it('says where the names and the address are changed', async () => {
    stubDetail();
    renderDetail();

    expect(
      await screen.findByText(
        'Names and the email address are changed on the member record, or by the person themselves.',
      ),
    ).toBeInTheDocument();
  });

  it('sends the roles alone with a save', async () => {
    const patched = stubDetail();
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => expect(patched).toHaveLength(1));
    expect(patched[0]).toEqual({ roles: ['member'] });
  });

  it('surfaces the escalation rule from the API', async () => {
    stubDetail({
      patch: () =>
        HttpResponse.json(
          {
            roles: [
              'Only a system administrator can grant or take away the System administrator role.',
            ],
          },
          { status: 400 },
        ),
    });
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    await userEvent.click(screen.getByRole('checkbox', { name: /dart leader/i }));
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /grant or take away the system administrator role/i,
    );
  });

  it("clears the server's refusal when the edits are canceled", async () => {
    stubDetail({
      patch: () =>
        HttpResponse.json(
          {
            roles: [
              'Only a system administrator can grant or take away the System administrator role.',
            ],
          },
          { status: 400 },
        ),
    });
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    await userEvent.click(screen.getByRole('checkbox', { name: /dart leader/i }));
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));
    await screen.findByText(/grant or take away the system administrator role/i);
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByText(/grant or take away the system administrator role/i)).toBeNull();
  });

  it("moves the focus to the server's refusal when no field carries it", async () => {
    stubDetail({
      patch: () =>
        HttpResponse.json(
          {
            roles: [
              'Only a system administrator can grant or take away the System administrator role.',
            ],
          },
          { status: 400 },
        ),
    });
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    await userEvent.click(screen.getByRole('checkbox', { name: /dart leader/i }));
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() =>
      expect(screen.getByText(/grant or take away the system administrator role/i)).toHaveFocus(),
    );
  });

  it('offers no action on your own account', async () => {
    const me = makeUser({ id: 7, roles: ['member', 'user_admin'] });
    stubDetail({ me });
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    expect(screen.queryByRole('button', { name: 'Deactivate account' })).not.toBeInTheDocument();
    expect(screen.getByText('You cannot deactivate or block your own account.')).toBeVisible();
  });

  it('has no Active box in the form', async () => {
    stubDetail();
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    expect(screen.queryByRole('checkbox', { name: /active/i })).not.toBeInTheDocument();
  });

  it('never sends the active flag with a save', async () => {
    const patched = stubDetail();
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => expect(patched).toHaveLength(1));
    expect(patched[0]).not.toHaveProperty('is_active');
  });

  describe('account status', () => {
    /**
     * Answer `POST .../{action}` with `answer`, and from then on serve `answer` as the
     * record too, as the server would once the action has gone through.
     */
    function stubAction(
      action: string,
      answer: AdminUserDetail | { detail: string },
      status = 200,
    ) {
      const calls: string[] = [];
      server.use(
        http.post(`${API}/admin/users/${TARGET.id}/${action}`, () => {
          calls.push(action);
          if (status === 200) {
            server.use(
              http.get(`${API}/admin/users/${TARGET.id}`, () => HttpResponse.json(answer)),
            );
          }
          return HttpResponse.json(answer, { status });
        }),
      );
      return calls;
    }

    it('deactivates once confirmed, and then offers reactivation', async () => {
      stubDetail();
      const calls = stubAction('deactivate', { ...TARGET, is_active: false });
      renderDetail();
      await screen.findByRole('heading', { name: 'Priya Raman' });

      await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));
      await userEvent.click(
        within(screen.getByRole('region', { name: 'Deactivate account' })).getByRole('button', {
          name: 'Yes, deactivate account',
        }),
      );

      expect(await screen.findByRole('button', { name: 'Reactivate account' })).toBeVisible();
      expect(calls).toEqual(['deactivate']);
    });

    it('draws a refused deactivation', async () => {
      stubDetail();
      stubAction(
        'deactivate',
        {
          detail: 'You cannot activate or deactivate an account that holds roles you do not hold.',
        },
        400,
      );
      renderDetail();
      await screen.findByRole('heading', { name: 'Priya Raman' });

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

    it('blocks reactivation once confirmed', async () => {
      stubDetail();
      const calls = stubAction('block', {
        ...TARGET,
        is_active: false,
        reactivation_blocked: true,
      });
      renderDetail();
      await screen.findByRole('heading', { name: 'Priya Raman' });

      await userEvent.click(screen.getByRole('button', { name: 'Block reactivation' }));
      expect(screen.getByText(/The account is deactivated first/)).toBeVisible();
      await userEvent.click(
        within(screen.getByRole('region', { name: 'Block reactivation' })).getByRole('button', {
          name: 'Yes, block reactivation',
        }),
      );

      expect(await screen.findByRole('button', { name: 'Allow reactivation' })).toBeVisible();
      expect(calls).toEqual(['block']);
    });

    it('offers no reactivation while the account is blocked', async () => {
      stubDetail({ target: { ...TARGET, is_active: false, reactivation_blocked: true } });
      renderDetail();
      await screen.findByRole('heading', { name: 'Priya Raman' });

      expect(screen.getByRole('button', { name: 'Reactivate account' })).toBeDisabled();
    });

    it('allows reactivation once confirmed', async () => {
      stubDetail({ target: { ...TARGET, is_active: false, reactivation_blocked: true } });
      const calls = stubAction('unblock', { ...TARGET, is_active: false });
      renderDetail();
      await screen.findByRole('heading', { name: 'Priya Raman' });

      await userEvent.click(screen.getByRole('button', { name: 'Allow reactivation' }));
      await userEvent.click(
        within(screen.getByRole('region', { name: 'Allow reactivation' })).getByRole('button', {
          name: 'Yes, allow reactivation',
        }),
      );

      expect(await screen.findByRole('button', { name: 'Block reactivation' })).toBeVisible();
      expect(calls).toEqual(['unblock']);
    });
  });

  it('sends a password reset and reports what the API said', async () => {
    stubDetail();
    server.use(
      http.post(`${API}/admin/users/${TARGET.id}/send-password-reset`, () =>
        HttpResponse.json({ detail: 'Password reset email sent to priya@example.org.' }),
      ),
    );
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    await userEvent.click(screen.getByRole('button', { name: /send password reset/i }));

    expect(
      await screen.findByText('Password reset email sent to priya@example.org.'),
    ).toBeInTheDocument();
  });

  it.each([
    ['send-password-reset', /send password reset/i, {}],
    [
      'send-email-verification',
      /resend verification message/i,
      { email_verified: false, email_verified_at: null },
    ],
  ])('reports a mail server that refused the %s message', async (action, button, overrides) => {
    const refused =
      'The mail server did not accept the message. ' +
      'A system administrator can see the attempt on the Sent emails page.';
    stubDetail({ target: { ...TARGET, ...overrides } });
    server.use(
      http.post(`${API}/admin/users/${TARGET.id}/${action}`, () =>
        HttpResponse.json({ detail: refused }, { status: 503 }),
      ),
    );
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    await userEvent.click(screen.getByRole('button', { name: button }));

    expect(await screen.findByText(refused)).toBeInTheDocument();
  });

  it('will not offer a reset for a deactivated account', async () => {
    stubDetail({ target: { ...TARGET, is_active: false } });
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    expect(screen.getByRole('button', { name: /send password reset/i })).toBeDisabled();
    expect(screen.getByText(/reactivate the account/i)).toBeInTheDocument();
  });

  it('explains a missing account rather than rendering an empty form', async () => {
    server.use(
      signedInAs(makeUser({ roles: ['member', 'user_admin'] })),
      http.get(`${API}/roles`, () => HttpResponse.json(ROLES)),
      http.get(`${API}/admin/users/404`, () =>
        HttpResponse.json(
          { detail: "That isn't here. It may have been deleted." },
          { status: 404 },
        ),
      ),
    );
    renderDetail('404');

    expect(await screen.findByText(/didn't load/i)).toBeInTheDocument();
  });

  it('marks a bounced address with the date and the report', async () => {
    stubDetail({ target: BOUNCED });
    renderDetail();

    expect(await screen.findByText('Bounced 10/01/2026')).toBeInTheDocument();
    expect(screen.getByText('5.1.1 550 User unknown')).toBeInTheDocument();
  });

  it('offers no Clear bounce for an address that has not bounced', async () => {
    stubDetail();
    renderDetail();

    await screen.findByRole('heading', { name: 'Priya Raman' });
    expect(screen.queryByRole('button', { name: 'Clear bounce' })).not.toBeInTheDocument();
  });

  it('clears a bounce only once the confirmation is pressed', async () => {
    stubDetail({ target: BOUNCED });
    const cleared: string[] = [];
    let stored = BOUNCED;
    server.use(
      http.get(`${API}/admin/users/${BOUNCED.id}`, () => HttpResponse.json(stored)),
      http.post(`${API}/admin/users/${BOUNCED.id}/clear-bounce`, ({ request }) => {
        cleared.push(request.url);
        stored = { ...BOUNCED, email_bounced_at: null, email_bounce_detail: '' };
        return HttpResponse.json(stored);
      }),
    );
    renderDetail();

    await userEvent.click(await screen.findByRole('button', { name: 'Clear bounce' }));
    expect(cleared).toEqual([]);
    const panel = screen.getByRole('region', { name: 'Clear bounce' });
    await userEvent.click(within(panel).getByRole('button', { name: 'Yes, clear bounce' }));

    await waitFor(() => expect(screen.queryByText('Bounced 10/01/2026')).not.toBeInTheDocument());
    expect(cleared).toHaveLength(1);
  });

  it('reports a Clear bounce the server refused', async () => {
    stubDetail({ target: BOUNCED });
    server.use(
      http.post(`${API}/admin/users/${BOUNCED.id}/clear-bounce`, () =>
        HttpResponse.json({ detail: 'Not allowed.' }, { status: 403 }),
      ),
    );
    renderDetail();

    await userEvent.click(await screen.findByRole('button', { name: 'Clear bounce' }));
    const panel = screen.getByRole('region', { name: 'Clear bounce' });
    await userEvent.click(within(panel).getByRole('button', { name: 'Yes, clear bounce' }));

    expect(await screen.findByText('Not allowed.')).toBeInTheDocument();
  });

  it('shows when the email address was verified, with no resend button', async () => {
    stubDetail();
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    expect(screen.getByText('Verified')).toHaveTextContent('Verified 07/01/2024');
    expect(
      screen.queryByRole('button', { name: /resend verification message/i }),
    ).not.toBeInTheDocument();
  });

  it('offers to resend a verification message for an unverified address', async () => {
    stubDetail({ target: { ...TARGET, email_verified: false, email_verified_at: null } });
    server.use(
      http.post(`${API}/admin/users/${TARGET.id}/send-email-verification`, () =>
        HttpResponse.json({ detail: 'Verification message sent to priya@example.org.' }),
      ),
    );
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    expect(screen.getByText('Unverified')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /resend verification message/i }));

    expect(
      await screen.findByText('Verification message sent to priya@example.org.'),
    ).toBeInTheDocument();
  });

  it('disables the resend button for a deactivated, unverified account', async () => {
    stubDetail({
      target: { ...TARGET, email_verified: false, email_verified_at: null, is_active: false },
    });
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    expect(screen.getByRole('button', { name: /resend verification message/i })).toBeDisabled();
  });

  it('reports the reason an admin resend is refused', async () => {
    stubDetail({ target: { ...TARGET, email_verified: false, email_verified_at: null } });
    server.use(
      http.post(`${API}/admin/users/${TARGET.id}/send-email-verification`, () =>
        HttpResponse.json({ detail: 'That address is already verified.' }, { status: 400 }),
      ),
    );
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });

    await userEvent.click(screen.getByRole('button', { name: /resend verification message/i }));

    expect(await screen.findByText('That address is already verified.')).toBeInTheDocument();
  });

  it('refetches the account after a refused resend, so the indicator cannot go stale', async () => {
    let requests = 0;
    server.use(
      signedInAs(makeUser({ id: 1, roles: ['member', 'user_admin'] })),
      http.get(`${API}/roles`, () => HttpResponse.json(ROLES)),
      http.get(`${API}/admin/users/${TARGET.id}`, () => {
        requests += 1;
        const target =
          requests === 1 ? { ...TARGET, email_verified: false, email_verified_at: null } : TARGET;
        return HttpResponse.json(target);
      }),
      http.post(`${API}/admin/users/${TARGET.id}/send-email-verification`, () =>
        HttpResponse.json({ detail: 'That address is already verified.' }, { status: 400 }),
      ),
    );
    renderDetail();
    await screen.findByRole('heading', { name: 'Priya Raman' });
    expect(screen.getByText('Unverified')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /resend verification message/i }));
    await screen.findByText('That address is already verified.');

    expect(await screen.findByText('Verified')).toHaveTextContent('Verified 07/01/2024');
  });

  describe('for a donor', () => {
    const DONOR = makeAdminUserDetail({
      id: 9,
      email: 'gil@example.org',
      first_name: 'Gil',
      last_name: 'Ivers',
      roles: [],
      kind: 'donor',
      email_verified_at: null,
    });

    it('says the account is a donor', async () => {
      stubDetail({ target: DONOR });
      renderDetail(String(DONOR.id));
      await screen.findByRole('heading', { name: 'Gil Ivers' });

      expect(screen.getByText('Donor')).toBeInTheDocument();
    });

    it('sends a mistyped address to the member record', async () => {
      stubDetail({ target: DONOR });
      renderDetail(String(DONOR.id));

      expect(
        await screen.findByText(/an account administrator corrects the email address/i),
      ).toBeInTheDocument();
    });

    it('offers no password reset', async () => {
      stubDetail({ target: DONOR });
      renderDetail(String(DONOR.id));
      await screen.findByRole('heading', { name: 'Gil Ivers' });

      expect(
        screen.queryByRole('button', { name: /send password reset/i }),
      ).not.toBeInTheDocument();
    });

    it('offers no verification message', async () => {
      stubDetail({ target: DONOR });
      renderDetail(String(DONOR.id));
      await screen.findByRole('heading', { name: 'Gil Ivers' });

      expect(screen.queryByRole('button', { name: /verification/i })).not.toBeInTheDocument();
    });
  });

  it('words a member with no term as the member record does, not as a friend', async () => {
    const noTerm = makeAdminUserDetail({
      ...TARGET,
      membership: { status: 'none', expires_on: null, plan: null, is_lifetime: false },
      has_terms: false,
    });
    stubDetail({ target: noTerm });
    renderDetail();
    expect(await screen.findByText('Not yet paid')).toBeInTheDocument();
  });

  it('grays out System administrator for a user administrator, and says why', async () => {
    stubDetail();
    renderDetail();
    const box = await screen.findByRole('checkbox', { name: 'System administrator' });
    expect(box).toBeDisabled();
  });

  it('names the reason under the grayed-out System administrator box', async () => {
    stubDetail();
    renderDetail();
    const box = await screen.findByRole('checkbox', { name: 'System administrator' });
    expect(box).toHaveAccessibleDescription(/only a system administrator can give or take away/i);
  });

  it('lets a system administrator change the System administrator role', async () => {
    stubDetail({ me: makeUser({ id: 1, roles: ['member', 'system_admin'] }) });
    renderDetail();
    const box = await screen.findByRole('checkbox', { name: 'System administrator' });
    expect(box).toBeEnabled();
  });

  it('lists who changed the roles and status in the History card', async () => {
    stubDetail({
      history: [
        {
          id: 2,
          changed_at: '2026-10-04T22:12:00Z',
          changed_by: { id: 1, name: 'Nina Kowalski' },
          by_command: false,
          kind: 'blocked',
          added: [],
          removed: [],
        },
        {
          id: 1,
          changed_at: '2026-10-03T16:00:00Z',
          changed_by: { id: 1, name: 'Nina Kowalski' },
          by_command: false,
          kind: 'roles',
          added: ['dart_leader'],
          removed: [],
        },
      ],
    });
    renderDetail();
    const card = (await screen.findByRole('heading', { name: 'History' })).closest('section');
    expect(card).not.toBeNull();
    const lines = await within(card as HTMLElement).findAllByRole('listitem');
    expect(lines.map((line) => line.textContent)).toEqual([
      `${formatDateTime('2026-10-04T22:12:00Z')} · Nina Kowalski · blocked reactivation`,
      `${formatDateTime('2026-10-03T16:00:00Z')} · Nina Kowalski · gave DART leader`,
    ]);
  });

  it('says so when no change is recorded', async () => {
    stubDetail();
    renderDetail();
    expect(
      await screen.findByText("No change to this account's roles or status is recorded."),
    ).toBeInTheDocument();
  });

  it('explains Deactivate account and Block reactivation before either is pressed', async () => {
    stubDetail();
    renderDetail();
    expect(await screen.findByText(/they, or you, can reactivate it later/i)).toBeInTheDocument();
  });

  it('explains Block reactivation under its button', async () => {
    stubDetail();
    renderDetail();
    expect(await screen.findByText(/cannot bring it back themselves/i)).toBeInTheDocument();
  });
});
