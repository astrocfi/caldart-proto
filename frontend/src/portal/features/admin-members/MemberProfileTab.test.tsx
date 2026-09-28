import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { makeDetail } from '@test/fixtures/members';
import {
  API,
  emptyVerificationCalls,
  makeLeaderStatus,
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

  it('takes a field corrected in the panel up into the form below', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    const corrected = makeLeaderStatus({
      certificate: { ...makeLeaderStatus().certificate, number: '7654321' },
      photo_id: { type: 'passport', verification: makeLeaderStatus().photo_id.verification },
    });
    server.use(...verificationHandlers(calls, { status: corrected }));
    renderWithProviders(<MemberProfileTab member={makeDetail()} />);

    await user.click(await within(verificationCard()).findByRole('button', { name: 'Verify' }));
    const panel = verificationCard();
    await user.clear(within(panel).getByLabelText('Certificate number'));
    await user.type(within(panel).getByLabelText('Certificate number'), '7654321');
    await user.click(within(panel).getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(calls.members).toHaveLength(1));
    expect(await screen.findByLabelText('Certificate number')).toHaveValue('7654321');
    expect(screen.getByLabelText('Photo ID')).toHaveValue('passport');
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
