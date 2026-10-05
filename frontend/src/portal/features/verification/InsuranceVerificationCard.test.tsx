import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import {
  NOT_VERIFIED,
  emptyVerificationCalls,
  makeUser,
  makeVerifiedAircraft,
  signedInAs,
  verificationHandlers,
} from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { InsuranceVerificationCard } from './InsuranceVerificationCard';

describe('InsuranceVerificationCard', () => {
  it('lists the insurance with its carrier, policy, limit, expiration, and mark', () => {
    renderWithProviders(<InsuranceVerificationCard aircraft={makeVerifiedAircraft()} />);
    const row = screen.getByRole('listitem');
    expect(row).toHaveTextContent(
      'InsuranceAvemco · AV-00012345 · Liability $1,000,000 per occurrence, $100,000 per person · expires 03/01/2027Verified by Dana Leader on 05/01/2026',
    );
  });

  it('prints the per-occurrence limit alone when no per-person limit is set', () => {
    renderWithProviders(
      <InsuranceVerificationCard
        aircraft={makeVerifiedAircraft({ insurance_liability_per_person_cents: 0 })}
      />,
    );
    expect(screen.getByRole('listitem')).toHaveTextContent(
      'InsuranceAvemco · AV-00012345 · Liability $1,000,000 per occurrence · expires 03/01/2027',
    );
  });

  it('reads No insurance on file for an aircraft with none on record', () => {
    renderWithProviders(
      <InsuranceVerificationCard
        aircraft={makeVerifiedAircraft({
          insurance_carrier: '',
          insurance_policy_number: '',
          insurance_liability_per_occurrence_cents: 0,
          insurance_liability_per_person_cents: 0,
          insurance_expiration: null,
          insurance_verification: NOT_VERIFIED,
        })}
      />,
    );
    expect(screen.getByRole('listitem')).toHaveTextContent(/^InsuranceNo insurance on file$/);
  });

  it('says Expired beside a lapsed policy that somebody verified', () => {
    renderWithProviders(
      <InsuranceVerificationCard
        aircraft={makeVerifiedAircraft({
          insurance_expiration: '2025-02-02',
          insurance_is_current: false,
        })}
      />,
    );
    expect(screen.getByRole('listitem')).toHaveTextContent(
      /expires 02\/02\/2025Expired\s*Verified by Dana Leader on 05\/01\/2026$/,
    );
  });

  it('offers no Verify to a reader without a verifying role', () => {
    renderWithProviders(<InsuranceVerificationCard aircraft={makeVerifiedAircraft()} />);
    expect(screen.queryByRole('button', { name: 'Verify' })).not.toBeInTheDocument();
  });

  it('opens the panel on Verify and hands the saved aircraft back', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    const handleSaved = vi.fn();
    server.use(
      signedInAs(makeUser({ roles: ['member', 'account_admin'] })),
      ...verificationHandlers(calls),
    );
    renderWithProviders(
      <InsuranceVerificationCard
        aircraft={makeVerifiedAircraft({ insurance_verification: NOT_VERIFIED })}
        onSaved={handleSaved}
      />,
    );

    await user.click(await screen.findByRole('button', { name: 'Verify' }));
    await user.click(screen.getByLabelText('Insurance verified'));
    await user.click(screen.getByRole('button', { name: 'Save verification' }));

    expect(await screen.findByText('Verification saved')).toBeInTheDocument();
    expect(calls.aircraft).toEqual([{ aircraftId: 1, body: { verified: true } }]);
    expect(handleSaved).toHaveBeenCalledWith(makeVerifiedAircraft());
    expect(screen.getByRole('listitem')).toBeInTheDocument();
  });
});
