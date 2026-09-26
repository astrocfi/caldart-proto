import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
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

function renderDetail(route = '/admin/members/1') {
  return renderWithProviders(
    <Routes>
      <Route path="/admin/members/:id" element={<MemberDetailPage />} />
      <Route path="/admin/members" element={<p>member list</p>} />
    </Routes>,
    { route },
  );
}

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

  it('says when the profile was last written', async () => {
    server.use(...detailHandlers());
    renderDetail();

    const header = (await screen.findByText('Current')).closest('.cluster');
    expect(header).toHaveTextContent('updated 2026/08/11');
  });

  it('says a profile nobody has written has never been edited', async () => {
    server.use(...detailHandlers(makeDetail({ profile_updated_at: null })));
    renderDetail();

    const header = (await screen.findByText('Current')).closest('.cluster');
    expect(header).toHaveTextContent('never edited');
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
    // The member also joined on 2024/07/01, so scope past that coincidence.
    expect(screen.getByText('Verified')).toHaveTextContent('Verified 2024/07/01');
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
    expect(await screen.findByRole('link', { name: '2025' })).toHaveAttribute(
      'href',
      '/api/v1/admin/payments/ledger/1/statements/2025.pdf',
    );
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

  it('sends an explicit start date when one is given', async () => {
    const user = userEvent.setup();
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=memberships');

    await screen.findByRole('option', { name: 'Life' });
    await user.selectOptions(screen.getByLabelText(/Plan/), 'life');
    await user.type(screen.getByLabelText(/Start date/), '2027-01-01');
    await user.click(screen.getByRole('button', { name: 'Grant term' }));

    await waitFor(() => expect(captured.grantedTerm).not.toBeNull());
    expect(captured.grantedTerm?.plan).toBe('life');
    expect(captured.grantedTerm?.starts_on).toBe('2027-01-01');
  });

  it('will not grant a term until a plan is chosen', async () => {
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=memberships');
    expect(await screen.findByRole('button', { name: 'Grant term' })).toBeDisabled();
  });

  it('edits the end date of an existing term', async () => {
    const user = userEvent.setup();
    server.use(...detailHandlers());
    renderDetail('/admin/members/1?tab=memberships');

    await user.click(await screen.findByRole('button', { name: 'Edit' }));
    const endDate = screen.getByLabelText('End date');
    await user.clear(endDate);
    await user.type(endDate, '2027-12-31');
    await user.selectOptions(screen.getByLabelText('Term status'), 'canceled');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(captured.patchedTerm).not.toBeNull());
    expect(captured.patchedTerm).toMatchObject({ ends_on: '2027-12-31', status: 'canceled' });
  });

  it('requires the email address to be typed before deleting', async () => {
    const user = userEvent.setup();
    // Only a member who never paid can be deleted at all.
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
        HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
      ),
    );
    renderDetail();
    expect(await screen.findByText('That member could not be loaded')).toBeInTheDocument();
  });
});
