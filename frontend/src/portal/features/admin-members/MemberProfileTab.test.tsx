import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { makeDetail } from '@test/fixtures/members';
import {
  API,
  emptyVerificationCalls,
  makeUser,
  signedInAs,
  verificationHandlers,
} from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { MemberProfileTab } from './MemberProfileTab';

/** The Verification card, found by its heading. */
function verificationCard(): HTMLElement {
  const card = screen.getByRole('heading', { name: 'Verification' }).closest('section');
  if (card === null) throw new Error('the Verification heading is not inside a card');
  return card;
}

describe('MemberProfileTab', () => {
  beforeEach(() => {
    server.use(
      signedInAs(makeUser({ roles: ['member', 'account_admin'] })),
      http.get(`${API}/darts`, () => HttpResponse.json([])),
    );
  });

  it('lists the three items with their marks above the form', () => {
    renderWithProviders(<MemberProfileTab member={makeDetail()} />);
    const rows = within(verificationCard()).getAllByRole('listitem');
    expect(rows.map((row) => row.textContent)).toEqual([
      'Pilot certificatePrivate · 1234567Not verified',
      'MedicalThird class · expires 01/31/2027Not verified',
      "Photo IDDriver's licenseNot verified",
    ]);
  });

  it('offers the kind of photo ID in the Aviation fieldset', () => {
    renderWithProviders(<MemberProfileTab member={makeDetail()} />);
    expect(screen.getByLabelText('Photo ID')).toHaveValue('drivers_license');
  });

  it('opens Verify on the checks alone, leaving the details to the form below', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MemberProfileTab member={makeDetail()} />);

    await user.click(await within(verificationCard()).findByRole('button', { name: 'Verify' }));

    expect(within(verificationCard()).queryByLabelText('Certificate number')).toBeNull();
  });

  it('sends only which items are verified from the member record', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    server.use(...verificationHandlers(calls));
    renderWithProviders(<MemberProfileTab member={makeDetail()} />);

    await user.click(await within(verificationCard()).findByRole('button', { name: 'Verify' }));
    await user.click(
      within(verificationCard()).getByRole('checkbox', { name: /medical verified/i }),
    );
    await user.click(within(verificationCard()).getByRole('button', { name: 'Save verification' }));

    await waitFor(() => expect(calls.members).toHaveLength(1));
    expect(calls.members[0]?.body).toEqual({ verified: ['medical'] });
  });

  it('lists the aircraft on the profile in a card of their own, linked to each record', () => {
    renderWithProviders(<MemberProfileTab member={makeDetail()} />);
    const card = screen.getByRole('heading', { name: 'Aircraft' }).closest('section');
    expect(card).not.toBeNull();
    const links = within(card as HTMLElement).getAllByRole('link');
    expect(links.map((link) => link.getAttribute('href'))).toEqual(
      (makeDetail().profile?.aircraft ?? []).map((one) => `/admin/aircraft/${one.id}`),
    );
  });

  it('shows the member’s callsign in the Amateur radio fieldset', () => {
    const detail = makeDetail();
    renderWithProviders(
      <MemberProfileTab
        member={{
          ...detail,
          profile: detail.profile && { ...detail.profile, ham_callsign: 'W6ABC' },
        }}
      />,
    );
    const radio = screen.getByRole('group', { name: 'Amateur radio' });
    expect(within(radio).getByLabelText('Amateur radio callsign')).toHaveValue('W6ABC');
  });

  it('saves an edited callsign in the nested profile, upper case', async () => {
    const user = userEvent.setup();
    const sent: { profile?: Record<string, unknown> } = {};
    server.use(
      http.patch(`${API}/admin/members/:id`, async ({ request }) => {
        Object.assign(sent, (await request.json()) as { profile?: Record<string, unknown> });
        return HttpResponse.json(makeDetail());
      }),
    );
    renderWithProviders(<MemberProfileTab member={makeDetail()} />);

    await user.type(screen.getByLabelText('Amateur radio callsign'), 'kd6ab');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(sent.profile).toMatchObject({ ham_callsign: 'KD6AB' }));
  });

  it('sends the names only as account fields, never inside the profile', async () => {
    const user = userEvent.setup();
    const sent: { profile?: Record<string, unknown> } = {};
    server.use(
      http.patch(`${API}/admin/members/:id`, async ({ request }) => {
        Object.assign(sent, (await request.json()) as { profile?: Record<string, unknown> });
        return HttpResponse.json(makeDetail());
      }),
    );
    renderWithProviders(<MemberProfileTab member={makeDetail()} />);

    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(sent.profile).toBeDefined());
    expect(sent.profile).not.toHaveProperty('first_name');
  });

  it('offers no Account is active box: the Delete or deactivate tab deactivates', () => {
    renderWithProviders(<MemberProfileTab member={makeDetail()} />);
    expect(screen.queryByRole('checkbox', { name: /account is active/i })).not.toBeInTheDocument();
  });

  it('shows no Verification card for a member with no profile yet', () => {
    renderWithProviders(<MemberProfileTab member={makeDetail({ profile: null })} />);
    expect(screen.queryByRole('heading', { name: 'Verification' })).not.toBeInTheDocument();
  });

  it('offers no Verify for a deactivated member, whom the endpoint would refuse', () => {
    renderWithProviders(<MemberProfileTab member={makeDetail({ is_active: false })} />);
    expect(
      within(verificationCard()).queryByRole('button', { name: 'Verify' }),
    ).not.toBeInTheDocument();
  });

  it('offers no Verify for a donor, whom the endpoint would refuse', () => {
    renderWithProviders(<MemberProfileTab member={makeDetail({ kind: 'donor' })} />);
    expect(
      within(verificationCard()).queryByRole('button', { name: 'Verify' }),
    ).not.toBeInTheDocument();
  });
});
