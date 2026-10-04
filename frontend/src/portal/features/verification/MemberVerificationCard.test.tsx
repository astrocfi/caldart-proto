import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import {
  NONE_VERIFIED,
  emptyVerificationCalls,
  makeLeaderStatus,
  makeUser,
  makeVerifiedProfile,
  signedInAs,
  verificationHandlers,
} from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { AdminProfile } from '@/portal/api/types';
import { MemberVerificationCard } from './MemberVerificationCard';

function makeAdminProfile(overrides: Partial<AdminProfile> = {}): AdminProfile {
  return { ...makeVerifiedProfile(), notes: '', how_heard: '', ...overrides };
}

describe('MemberVerificationCard', () => {
  it('lists each item with what the record holds and its mark', () => {
    renderWithProviders(
      <MemberVerificationCard userId={7} profile={makeAdminProfile()} checkable />,
    );
    const rows = screen.getAllByRole('listitem');
    expect(rows.map((row) => row.textContent)).toEqual([
      'Pilot certificatePrivate · 3141592Verified by Dana Leader on 05/01/2026',
      'MedicalThird class · expires 05/31/2029Verified by Dana Leader on 05/01/2026',
      'Photo IDPassportVerified by Dana Leader on 05/01/2026',
    ]);
  });

  it('reads Not verified for an item nobody has checked', () => {
    renderWithProviders(
      <MemberVerificationCard
        userId={7}
        profile={makeAdminProfile({ verification: NONE_VERIFIED })}
        checkable
      />,
    );
    const rows = screen.getAllByRole('listitem');
    expect(within(rows[2]!).getByText('Not verified')).toBeInTheDocument();
  });

  it('draws no mark for an item the person does not hold', () => {
    renderWithProviders(
      <MemberVerificationCard
        userId={7}
        profile={makeAdminProfile({
          pilot_certificate_type: 'none',
          certificate_number: '',
          medical_type: 'none',
          medical_expiration: null,
          photo_id_type: 'not_provided',
          verification: NONE_VERIFIED,
        })}
        checkable
      />,
    );
    expect(screen.getAllByRole('listitem').map((row) => row.textContent)).toEqual([
      'Pilot certificateNot a pilot',
      'MedicalNone',
      'Photo IDNot provided',
    ]);
  });

  it('says Expired beside a lapsed medical that somebody verified', () => {
    renderWithProviders(
      <MemberVerificationCard
        userId={7}
        profile={makeAdminProfile({ medical_type: 'basicmed', medical_expiration: '2025-02-02' })}
        checkable
      />,
    );
    const medical = screen.getAllByRole('listitem')[1]!;
    expect(medical).toHaveTextContent(
      /^MedicalBasicMed · expires 02\/02\/2025Expired\s*Verified by Dana Leader on 05\/01\/2026$/,
    );
  });

  it('offers no Verify to a reader without a verifying role', () => {
    renderWithProviders(
      <MemberVerificationCard userId={7} profile={makeAdminProfile()} checkable />,
    );
    expect(screen.queryByRole('button', { name: 'Verify' })).not.toBeInTheDocument();
  });

  it('offers no Verify for a member the endpoint would refuse with a 404', () => {
    server.use(signedInAs(makeUser({ roles: ['member', 'account_admin'] })));
    renderWithProviders(
      <MemberVerificationCard userId={7} profile={makeAdminProfile()} checkable={false} />,
    );
    expect(screen.queryByRole('button', { name: 'Verify' })).not.toBeInTheDocument();
  });

  it('opens the panel on Verify and hands the saved card back', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    const handleSaved = vi.fn();
    server.use(
      signedInAs(makeUser({ roles: ['member', 'account_admin'] })),
      ...verificationHandlers(calls),
    );
    renderWithProviders(
      <MemberVerificationCard
        userId={7}
        profile={makeAdminProfile({ verification: NONE_VERIFIED })}
        checkable
        onSaved={handleSaved}
      />,
    );

    await user.click(await screen.findByRole('button', { name: 'Verify' }));
    await user.click(screen.getByLabelText('Medical verified'));
    await user.click(screen.getByRole('button', { name: 'Save verification' }));

    expect(await screen.findByText('Verification saved')).toBeInTheDocument();
    expect(calls.members).toEqual([{ userId: 7, body: { verified: ['medical'] } }]);
    expect(handleSaved).toHaveBeenCalledWith(makeLeaderStatus());
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
  });
});
