import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { QueryClient } from '@tanstack/react-query';
import { HttpResponse, http } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders, signedInClient } from '@test/render';
import { server } from '@test/server';
import type { MemberTerm } from '@/portal/api/types';
import { todayIso } from '@/portal/components/DateText';
import { MemberDetailPage } from './MemberDetailPage';
import { makeDetail } from '@test/fixtures/members';
import { makeLedger } from '@test/fixtures/finance';

const DARTS = [{ id: 3, name: 'Palo Alto', airport_identifiers: 'PAO', city: 'Palo Alto' }];
const PLANS = [
  { slug: 'annual', name: 'Annual', price_cents: 4500, duration_days: 365, description: '' },
  { slug: 'life', name: 'Life', price_cents: 65000, duration_days: null, description: '' },
];

interface Captured {
  patchedMember: Record<string, unknown> | null;
  grantedTerm: Record<string, unknown> | null;
  patchedTerm: Record<string, unknown> | null;
  deleted: boolean;
}

let captured: Captured;

function detailHandlers(member = makeDetail()) {
  return [
    http.get(`${API}/darts`, () => HttpResponse.json(DARTS)),
    http.get(`${API}/plans`, () => HttpResponse.json(PLANS)),
    http.get(`${API}/admin/members/${member.id}`, () => HttpResponse.json(member)),
    http.get(`${API}/admin/payments/ledger/${member.id}`, () =>
      HttpResponse.json(
        makeLedger({
          user: { ...makeLedger().user, id: member.id },
          statement_years: [2026, 2025],
        }),
      ),
    ),
    http.patch(`${API}/admin/members/${member.id}`, async ({ request }) => {
      captured.patchedMember = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(member);
    }),
    http.delete(`${API}/admin/members/${member.id}`, () => {
      captured.deleted = true;
      return new HttpResponse(null, { status: 204 });
    }),
    http.post(`${API}/admin/members/${member.id}/memberships`, async ({ request }) => {
      captured.grantedTerm = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({ ...member.memberships[0], id: 99 }, { status: 201 });
    }),
    http.patch(`${API}/admin/memberships/:termId`, async ({ request }) => {
      captured.patchedTerm = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(member.memberships[0]);
    }),
  ];
}

function renderDetail(route = '/admin/members/1', client?: QueryClient) {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/members/:id" element={<MemberDetailPage />} />
      <Route path="/admin/members" element={<p>member list</p>} />
      <Route path="/admin/payments/donors" element={<p>donors report</p>} />
    </Routes>,
    { route, client },
  );
}

/** A donor: no role, no membership term, and one gift through the public site. */
const DONOR = makeDetail({
  email: 'rosa@example.org',
  first_name: 'Rosa',
  last_name: 'Delgado',
  name: 'Rosa Delgado',
  kind: 'donor',
  roles: [],
  memberships: [],
});

beforeEach(() => {
  captured = { patchedMember: null, grantedTerm: null, patchedTerm: null, deleted: false };
});

describe('MemberDetailPage', () => {
  it('shows the member with their membership status', async () => {
    server.use(...detailHandlers());
    renderDetail();

    expect(await screen.findByRole('heading', { name: 'Ana Bracco' })).toBeInTheDocument();
    expect(screen.getByText('Current')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'ana@example.org' })).toBeInTheDocument();
  });

  it('names the browser tab after the member and the record', async () => {
    server.use(...detailHandlers());
    renderDetail();

    await screen.findByRole('heading', { name: 'Ana Bracco' });
    await waitFor(() => expect(document.title).toBe('Ana Bracco · Member record · CalDART'));
  });

  it('says when the profile was last written', async () => {
    server.use(...detailHandlers());
    renderDetail();

    const header = (await screen.findByText('Current')).closest('.cluster');
    expect(header).toHaveTextContent('Profile updated 08/11/2026');
  });

  it('says a profile nobody has written has never been edited', async () => {
    server.use(...detailHandlers(makeDetail({ profile_updated_at: null })));
    renderDetail();

    const header = (await screen.findByText('Current')).closest('.cluster');
    expect(header).toHaveTextContent('Profile never edited');
  });

  it('points a member with no term at Memberships rather than calling them a friend', async () => {
    const noTerm = makeDetail({
      membership: { status: 'none', expires_on: null, plan: null, is_lifetime: false },
      memberships: [],
      joined_on: null,
    });
    server.use(...detailHandlers(noTerm));
    renderDetail();

    expect(
      await screen.findByText('Not yet paid: grant a term on Memberships'),
    ).toBeInTheDocument();
  });

  it('leaves out the expiry and joining dates a member with no term does not have', async () => {
    const noTerm = makeDetail({
      membership: { status: 'none', expires_on: null, plan: null, is_lifetime: false },
      memberships: [],
      joined_on: null,
    });
    server.use(...detailHandlers(noTerm));
    renderDetail();

    const header = (await screen.findByText(/Not yet paid/)).closest('.cluster');
    expect(header?.textContent).not.toMatch(/expires|joined/);
  });

  it('says a deactivated member’s membership is set aside, not that they are a friend', async () => {
    const base = makeDetail();
    const setAside = makeDetail({
      is_active: false,
      membership: { status: 'friend', expires_on: null, plan: null, is_lifetime: false },
      memberships: base.memberships.map((term) => ({ ...term, status: 'suspended' as const })),
    });
    server.use(...detailHandlers(setAside));
    renderDetail();

    expect(await screen.findByText('Membership set aside while deactivated')).toBeInTheDocument();
  });

  it('marks a bounced address beside it in the header, with the report', async () => {
    server.use(
      ...detailHandlers(
        makeDetail({
          email_bounced_at: '2026-10-01T12:00:00Z',
          email_bounce_detail: '5.1.1 550 User unknown',
        }),
      ),
    );
    renderDetail();

    const address = await screen.findByRole('link', { name: 'ana@example.org' });
    expect(address.closest('p')).toHaveTextContent('Bounced 10/01/2026 5.1.1 550 User unknown');
  });

  it('shows no bounce for an address that has not bounced', async () => {
    server.use(...detailHandlers());
    renderDetail();

    await screen.findByRole('link', { name: 'ana@example.org' });
    expect(screen.queryByText(/^Bounced/)).not.toBeInTheDocument();
  });

  it('opens on the profile tab with the admin-only notes filled in', async () => {
    server.use(...detailHandlers());
    renderDetail();

    expect(await screen.findByLabelText('Administrator notes')).toHaveValue(
      'Called about the Napa exercise.',
    );
    expect(screen.getByRole('tab', { name: 'Profile' })).toHaveAttribute('aria-selected', 'true');
  });

  it('shows when the email address was verified', async () => {
    server.use(...detailHandlers());
    renderDetail();

    await screen.findByLabelText('Administrator notes');
    // The member also joined on 07/01/2024, so scope past that coincidence.
    expect(screen.getByText('Verified')).toHaveTextContent('Verified 07/01/2024');
  });

  it('shows an unverified email address with no resend button', async () => {
    server.use(...detailHandlers(makeDetail({ email_verified_at: null })));
    renderDetail();

    await screen.findByLabelText('Administrator notes');
    expect(screen.getByText('Unverified')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /resend verification message/i }),
    ).not.toBeInTheDocument();
  });

  it('moves between tabs with the arrow keys', async () => {
    const user = userEvent.setup();
    server.use(...detailHandlers());
    renderDetail();

    const profileTab = await screen.findByRole('tab', { name: 'Profile' });
    profileTab.focus();
    await user.keyboard('{ArrowRight}');

    expect(screen.getByRole('tab', { name: 'Memberships' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(await screen.findByRole('heading', { name: 'Grant a term' })).toBeInTheDocument();
  });

  it('opens straight onto a tab named in the URL', async () => {
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=payments');
    expect(await screen.findByRole('heading', { name: 'Payments' })).toBeInTheDocument();
  });

  it('reads the payments tab from the finance ledger', async () => {
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=payments');
    expect(await screen.findByRole('link', { name: 'CALDART-000412' })).toBeInTheDocument();
  });

  it('offers the member their contribution statements', async () => {
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=payments');
    expect(
      await screen.findByRole('link', { name: 'Download the 2025 contribution statement (PDF)' }),
    ).toHaveAttribute('href', '/api/v1/admin/payments/ledger/1/statements/2025.pdf');
  });

  it('saves the profile, notes included', async () => {
    const user = userEvent.setup();
    server.use(...detailHandlers());
    renderDetail();

    const notes = await screen.findByLabelText('Administrator notes');
    await user.clear(notes);
    await user.type(notes, 'Renewed over the phone.');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(captured.patchedMember).not.toBeNull());
    const profile = captured.patchedMember?.profile as Record<string, unknown>;
    expect(profile.notes).toBe('Renewed over the phone.');
    expect(captured.patchedMember?.email).toBe('ana@example.org');
    expect(await screen.findByText('Member saved.')).toBeInTheDocument();
  });

  it('refuses to save a blank first name, so the heading never reads a surname alone', async () => {
    const user = userEvent.setup();
    server.use(...detailHandlers());
    renderDetail();

    const first = await screen.findByLabelText(/^First name/);
    await user.clear(first);
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    expect(await screen.findByText('Enter a first name.')).toBeInTheDocument();
    expect(first).toHaveFocus();
    expect(captured.patchedMember).toBeNull();
  });

  it('grants a term from the memberships tab', async () => {
    const user = userEvent.setup();
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=memberships');

    await screen.findByRole('option', { name: 'Annual' });
    await user.selectOptions(screen.getByLabelText(/Plan/), 'annual');
    await user.type(screen.getByLabelText(/Note/), 'Comped by the board');
    await user.click(screen.getByRole('button', { name: 'Grant term' }));

    await waitFor(() => expect(captured.grantedTerm).not.toBeNull());
    expect(captured.grantedTerm).toEqual({
      plan: 'annual',
      starts_on: null,
      note: 'Comped by the board',
    });
  });

  it('names the granted term’s last day as MM/DD/YYYY', async () => {
    const user = userEvent.setup();
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=memberships');

    await screen.findByRole('option', { name: 'Annual' });
    await user.selectOptions(screen.getByLabelText(/Plan/), 'annual');
    await user.click(screen.getByRole('button', { name: 'Grant term' }));

    expect(await screen.findByText('Term granted through 06/30/2027.')).toBeInTheDocument();
  });

  it('sends an explicit start date when one is given', async () => {
    const user = userEvent.setup();
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=memberships');

    await screen.findByRole('option', { name: 'Life' });
    await user.selectOptions(screen.getByLabelText(/Plan/), 'life');
    await user.type(screen.getByLabelText(/Start date/), '2026-01-01');
    await user.click(screen.getByRole('button', { name: 'Grant term' }));

    await waitFor(() => expect(captured.grantedTerm).not.toBeNull());
    expect(captured.grantedTerm?.plan).toBe('life');
    expect(captured.grantedTerm?.starts_on).toBe('2026-01-01');
  });

  it('offers no start date later than today', async () => {
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=memberships');

    expect(await screen.findByLabelText(/Start date/)).toHaveAttribute('max', todayIso());
  });

  it('shows the refusal of a start date after today under Start date', async () => {
    const user = userEvent.setup();
    const refusal = 'A membership cannot start after today.';
    // The first handler msw holds for a request answers it, so the refusal goes first.
    server.use(
      http.post(`${API}/admin/members/1/memberships`, () =>
        HttpResponse.json({ starts_on: [refusal] }, { status: 400 }),
      ),
      ...detailHandlers(),
    );
    renderDetail('/admin/members/1?tab=memberships');

    await screen.findByRole('option', { name: 'Annual' });
    await user.selectOptions(screen.getByLabelText(/Plan/), 'annual');
    await user.click(screen.getByRole('button', { name: 'Grant term' }));

    await waitFor(() =>
      expect(screen.getByLabelText(/Start date/)).toHaveAccessibleDescription(
        expect.stringContaining(refusal),
      ),
    );
  });

  it('will not grant a term until a plan is chosen', async () => {
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=memberships');
    expect(await screen.findByRole('button', { name: 'Grant term' })).toBeDisabled();
  });

  it('says why Grant term is grayed out', async () => {
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=memberships');
    expect(await screen.findByRole('button', { name: 'Grant term' })).toHaveAccessibleDescription(
      'Choose a plan first.',
    );
  });

  it('labels each contribution statement with words, not the year alone', async () => {
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=payments');
    expect(await screen.findByText('Download 2025 statement')).toBeInTheDocument();
  });

  it('edits the end date of an existing term', async () => {
    const user = userEvent.setup();
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=memberships');

    await user.click(
      await screen.findByRole('button', { name: 'Edit the Annual term, 07/01/2026 to 06/30/2027' }),
    );
    const endDate = screen.getByLabelText('End date');
    await user.clear(endDate);
    await user.type(endDate, '2027-12-31');
    await user.selectOptions(screen.getByLabelText('Term status'), 'canceled');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(captured.patchedTerm).not.toBeNull());
    expect(captured.patchedTerm).toMatchObject({ ends_on: '2027-12-31', status: 'canceled' });
  });

  it("moves the focus into a term's end date as its edit opens", async () => {
    const user = userEvent.setup();
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=memberships');

    await user.click(await screen.findByRole('button', { name: /^Edit the / }));

    expect(screen.getByLabelText('End date')).toHaveFocus();
  });

  it("closes a term's edit on Escape and gives the focus back to its Edit", async () => {
    const user = userEvent.setup();
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=memberships');

    await user.click(await screen.findByRole('button', { name: /^Edit the / }));
    await user.keyboard('{Escape}');

    expect(screen.getByRole('button', { name: /^Edit the / })).toHaveFocus();
  });

  it('offers Suspended when editing a term a self-deactivation suspended', async () => {
    const user = userEvent.setup();
    server.use(
      ...detailHandlers(
        makeDetail({
          memberships: [
            {
              id: 11,
              plan: 'Annual',
              plan_slug: 'annual',
              starts_on: '2026-07-01',
              ends_on: '2027-06-30',
              status: 'suspended',
              source: 'payment',
              note: '',
              granted_by: null,
              payment: 21,
              created_at: '2026-07-01T12:00:00Z',
            },
          ],
        }),
      ),
    );
    renderDetail('/admin/members/1?tab=memberships');

    await user.click(
      await screen.findByRole('button', { name: 'Edit the Annual term, 07/01/2026 to 06/30/2027' }),
    );

    expect(screen.getByLabelText('Term status')).toHaveValue('suspended');
    expect(screen.getByRole('option', { name: 'Suspended' })).toBeInTheDocument();
  });

  describe('the membership history', () => {
    /** One term of the history, active and paid unless the case says otherwise. */
    function term(overrides: Partial<MemberTerm>): MemberTerm {
      return {
        id: 11,
        plan: 'Annual',
        plan_slug: 'annual',
        starts_on: '2026-07-01',
        ends_on: '2027-06-30',
        status: 'active',
        source: 'payment',
        note: '',
        granted_by: null,
        payment: 21,
        created_at: '2026-07-01T12:00:00Z',
        ...overrides,
      };
    }

    it.each([
      ['active', 'Active', 'current'],
      ['expired', 'Expired', 'expired'],
      ['canceled', 'Canceled', 'none'],
      ['suspended', 'Suspended', 'none'],
    ] as const)('shows a %s term as the word %s beside its dot', async (status, word, tone) => {
      server.use(...detailHandlers(makeDetail({ memberships: [term({ status })] })));
      renderDetail('/admin/members/1?tab=memberships');

      const table = within(await screen.findByRole('table'));
      expect(table.getByText(word)).toHaveAttribute('data-tone', tone);
    });

    it.each([
      ['payment', 'Paid'],
      ['manual', 'Granted by hand'],
      ['seed', 'Demo data'],
    ] as const)('names a %s source %s, not by its code', async (source, word) => {
      server.use(...detailHandlers(makeDetail({ memberships: [term({ source })] })));
      renderDetail('/admin/members/1?tab=memberships');

      const table = within(await screen.findByRole('table'));
      expect(table.getByRole('cell', { name: word })).toBeInTheDocument();
    });
  });

  it('requires the email address to be typed before deleting', async () => {
    const user = userEvent.setup();
    server.use(...detailHandlers(makeDetail({ payments: [] })));
    renderDetail('/admin/members/1?tab=danger');

    const button = await screen.findByRole('button', { name: 'Delete member' });
    expect(button).toBeDisabled();

    await user.type(screen.getByLabelText(/Type ana@example.org to confirm/), 'wrong@example.org');
    expect(button).toBeDisabled();

    await user.clear(screen.getByLabelText(/Type ana@example.org to confirm/));
    await user.type(screen.getByLabelText(/Type ana@example.org to confirm/), 'ana@example.org');
    expect(button).toBeEnabled();

    await user.click(button);
    await waitFor(() => expect(captured.deleted).toBe(true));
    expect(await screen.findByText('member list')).toBeInTheDocument();
  });

  it('deletes a member who has payments', async () => {
    const user = userEvent.setup();
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=danger');

    await user.type(
      await screen.findByLabelText(/Type ana@example.org to confirm/),
      'ana@example.org',
    );
    await user.click(screen.getByRole('button', { name: 'Delete member' }));

    await waitFor(() => expect(captured.deleted).toBe(true));
  });

  it('reports a refused delete', async () => {
    const user = userEvent.setup();
    // msw takes the first matching handler, so the refusal has to come before
    // the happy-path DELETE in `detailHandlers`.
    server.use(
      http.delete(`${API}/admin/members/1`, () =>
        HttpResponse.json({ detail: 'You cannot delete your own account.' }, { status: 403 }),
      ),
      ...detailHandlers(makeDetail({ payments: [] })),
    );
    renderDetail('/admin/members/1?tab=danger');

    await user.type(
      await screen.findByLabelText(/Type ana@example.org to confirm/),
      'ana@example.org',
    );
    await user.click(screen.getByRole('button', { name: 'Delete member' }));

    expect(await screen.findByText('You cannot delete your own account.')).toBeInTheDocument();
  });

  it('reports what the member has paid over their whole history', async () => {
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=payments');

    expect(await screen.findByText('$435.00')).toBeInTheDocument();
  });

  it('explains a member it cannot load', async () => {
    server.use(
      http.get(`${API}/darts`, () => HttpResponse.json(DARTS)),
      http.get(`${API}/plans`, () => HttpResponse.json(PLANS)),
      http.get(`${API}/admin/members/1`, () =>
        HttpResponse.json(
          { detail: "That isn't here. It may have been deleted." },
          { status: 404 },
        ),
      ),
    );
    renderDetail();
    expect(await screen.findByText("That member didn't load")).toBeInTheDocument();
  });

  it('shows the kind of a friend on the profile tab and saves a change of kind', async () => {
    const user = userEvent.setup();
    server.use(
      ...detailHandlers(
        makeDetail({
          kind: 'friend',
          membership: { status: 'friend', expires_on: null, plan: null, is_lifetime: false },
        }),
      ),
    );
    renderDetail();

    const kind = await screen.findByLabelText('Kind of account');
    expect(kind).toHaveValue('friend');
    await user.selectOptions(kind, 'member');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(captured.patchedMember?.kind).toBe('member'));
  });

  it('sends no kind when a save leaves the kind as it was', async () => {
    const user = userEvent.setup();
    server.use(...detailHandlers(makeDetail({ kind: 'member' })));
    renderDetail();

    await screen.findByLabelText('Kind of account');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(captured.patchedMember).not.toBeNull());
    expect(captured.patchedMember).not.toHaveProperty('kind');
  });

  it('marks a donor as a donor and offers no change of kind', async () => {
    server.use(...detailHandlers(makeDetail({ kind: 'donor', roles: [] })));
    renderDetail();

    const header = (await screen.findByText('Current')).closest('.cluster');
    expect(header).toHaveTextContent('Donor');
    expect(screen.queryByLabelText('Kind of account')).not.toBeInTheDocument();
  });

  it('leads a treasurer back to the members from a record that is not a donor', async () => {
    server.use(...detailHandlers());
    renderDetail('/admin/members/1', signedInClient('treasurer', 'account_admin'));

    expect(await screen.findByRole('link', { name: 'Back to members' })).toHaveAttribute(
      'href',
      '/admin/members',
    );
  });

  it('does not fetch the record again once it is deleted', async () => {
    const user = userEvent.setup();
    let reads = 0;
    // Registered first, so it answers the record's reads ahead of `detailHandlers`.
    server.use(
      http.get(`${API}/admin/members/1`, () => {
        reads += 1;
        return HttpResponse.json(makeDetail({ payments: [] }));
      }),
      ...detailHandlers(makeDetail({ payments: [] })),
    );
    renderDetail('/admin/members/1?tab=danger');

    await user.type(
      await screen.findByLabelText(/Type ana@example.org to confirm/),
      'ana@example.org',
    );
    const before = reads;
    await user.click(screen.getByRole('button', { name: 'Delete member' }));
    await screen.findByText('member list');

    expect(reads).toBe(before);
  });

  describe('for a donor', () => {
    it('keeps the delete disabled until the address is typed', async () => {
      server.use(...detailHandlers(DONOR));
      renderDetail('/admin/members/1?tab=danger');

      expect(await screen.findByRole('button', { name: 'Delete member' })).toBeDisabled();
    });

    it('deletes the donor once the address is typed', async () => {
      const user = userEvent.setup();
      server.use(...detailHandlers(DONOR));
      renderDetail('/admin/members/1?tab=danger');

      await user.type(
        await screen.findByLabelText(/Type rosa@example.org to confirm/),
        'rosa@example.org',
      );
      await user.click(screen.getByRole('button', { name: 'Delete member' }));

      await waitFor(() => expect(captured.deleted).toBe(true));
    });

    it('says the gifts stay in the books under the tombstone', async () => {
      server.use(...detailHandlers(DONOR));
      renderDetail('/admin/members/1?tab=danger');

      expect(
        await screen.findByText(
          'Rosa Delgado has 1 payment record. It stays in the books under the name Deleted member 1.',
        ),
      ).toBeInTheDocument();
    });

    it('returns a treasurer to the donors report after the delete', async () => {
      const user = userEvent.setup();
      server.use(...detailHandlers(DONOR));
      renderDetail('/admin/members/1?tab=danger', signedInClient('treasurer', 'account_admin'));

      await user.type(
        await screen.findByLabelText(/Type rosa@example.org to confirm/),
        'rosa@example.org',
      );
      await user.click(screen.getByRole('button', { name: 'Delete member' }));

      expect(await screen.findByText('donors report')).toBeInTheDocument();
    });

    it('returns an administrator without the donors report to the members', async () => {
      const user = userEvent.setup();
      server.use(...detailHandlers(DONOR));
      renderDetail('/admin/members/1?tab=danger', signedInClient('account_admin'));

      await user.type(
        await screen.findByLabelText(/Type rosa@example.org to confirm/),
        'rosa@example.org',
      );
      await user.click(screen.getByRole('button', { name: 'Delete member' }));

      expect(await screen.findByText('member list')).toBeInTheDocument();
    });

    it('leads a treasurer back to the donors report', async () => {
      server.use(...detailHandlers(DONOR));
      renderDetail('/admin/members/1', signedInClient('treasurer', 'account_admin'));

      expect(await screen.findByRole('link', { name: 'Back to donors' })).toHaveAttribute(
        'href',
        '/admin/payments/donors',
      );
    });

    it('leads an administrator without the donors report back to the members', async () => {
      server.use(...detailHandlers(DONOR));
      renderDetail('/admin/members/1', signedInClient('account_admin'));

      expect(await screen.findByRole('link', { name: 'Back to members' })).toBeInTheDocument();
    });

    it('offers no term to grant', async () => {
      server.use(...detailHandlers(DONOR));
      renderDetail('/admin/members/1?tab=memberships');

      await screen.findByRole('heading', { name: 'Membership history' });

      expect(screen.queryByRole('button', { name: 'Grant term' })).not.toBeInTheDocument();
    });

    it('says why a donor holds no term', async () => {
      server.use(...detailHandlers(DONOR));
      renderDetail('/admin/members/1?tab=memberships');

      expect(
        await screen.findByText(
          'A donor holds no membership, and becomes a member only by registering.',
        ),
      ).toBeInTheDocument();
    });
  });

  describe('for a deleted member', () => {
    const TOMBSTONE = makeDetail({
      id: 1,
      email: 'deleted-41@deleted.invalid',
      first_name: 'Deleted member',
      last_name: '41',
      name: 'Deleted member 41',
      kind: 'donor',
      is_tombstone: true,
      is_active: false,
      roles: [],
      memberships: [],
    });
    const NOTE =
      "This record keeps a deleted member's payments in the books and cannot be changed.";

    it('offers no profile form to save', async () => {
      server.use(...detailHandlers(TOMBSTONE));
      renderDetail();

      await screen.findByText(NOTE);

      expect(screen.queryByRole('button', { name: 'Save changes' })).not.toBeInTheDocument();
    });

    it('offers no term to grant', async () => {
      server.use(...detailHandlers(TOMBSTONE));
      renderDetail('/admin/members/1?tab=memberships');

      await screen.findByRole('heading', { name: 'Membership history' });

      expect(screen.queryByRole('button', { name: 'Grant term' })).not.toBeInTheDocument();
    });

    it('offers no delete', async () => {
      server.use(...detailHandlers(TOMBSTONE));
      renderDetail('/admin/members/1?tab=danger');

      await screen.findByText(NOTE);

      expect(screen.queryByRole('button', { name: 'Delete member' })).not.toBeInTheDocument();
    });
  });
});
