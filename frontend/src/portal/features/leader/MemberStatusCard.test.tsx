import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import {
  NOT_VERIFIED,
  emptyVerificationCalls,
  makeLeaderStatus,
  makeUser,
  makeVerifiedAircraftSummary,
  signedInAs,
  verificationHandlers,
} from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { RoleSlug } from '@/portal/api/types';
import { MemberStatusCard, isGo, noGoReasons } from './MemberStatusCard';

const TODAY = new Date('2026-06-01T09:00:00');

const makeAircraft = makeVerifiedAircraftSummary;
const makeStatus = makeLeaderStatus;
const VERIFIED_MEDICAL = makeLeaderStatus().medical.verification;

describe('isGo / noGoReasons', () => {
  it.each([
    [true, true, true, []],
    [false, true, false, ['Membership expired']],
    [true, false, false, ['Medical expired']],
    [false, false, false, ['Membership expired', 'Medical expired']],
  ])('membership=%s medical=%s -> go=%s', (membership, medical, expectedGo, expectedReasons) => {
    const status = makeStatus({
      membership: { status: membership ? 'current' : 'expired', expires_on: null, plan: 'Annual' },
      medical: {
        type: 'third',
        expiration: '2020-01-01',
        is_current: medical,
        verification: VERIFIED_MEDICAL,
      },
      go_no_go: { membership, medical, verified: true },
    });
    expect(isGo(status)).toBe(expectedGo);
    expect(noGoReasons(status)).toEqual(expectedReasons);
  });

  it('says a friend is a friend of CalDART, not a member', () => {
    const status = makeStatus({
      membership: { status: 'friend', expires_on: null, plan: null },
      go_no_go: { membership: false, medical: true, verified: true },
    });
    expect(noGoReasons(status)).toEqual(['Friend of CalDART, not a member']);
  });

  it('does not call a medical expired when no expiry was ever entered', () => {
    const status = makeStatus({
      medical: {
        type: 'third',
        expiration: null,
        is_current: false,
        verification: VERIFIED_MEDICAL,
      },
      go_no_go: { membership: true, medical: false, verified: true },
    });
    expect(noGoReasons(status)).toEqual(['No medical expiry on file']);
  });

  it('says "no medical on file" when none was ever entered', () => {
    const status = makeStatus({
      medical: {
        type: 'none',
        expiration: null,
        is_current: false,
        verification: VERIFIED_MEDICAL,
      },
      go_no_go: { membership: true, medical: false, verified: true },
    });
    expect(noGoReasons(status)).toEqual(['No medical on file']);
  });

  it('names each item nobody has verified, after the other reasons', () => {
    const current = makeStatus();
    const status = makeStatus({
      membership: { status: 'expired', expires_on: null, plan: 'Annual' },
      certificate: { ...current.certificate, verification: NOT_VERIFIED },
      medical: { ...current.medical, verification: NOT_VERIFIED },
      photo_id: { type: 'passport', verification: NOT_VERIFIED },
      go_no_go: { membership: false, medical: true, verified: false },
    });
    expect(noGoReasons(status)).toEqual([
      'Membership expired',
      'Medical not verified',
      'Certificate not verified',
      'Photo ID not verified',
    ]);
  });

  it('gives a non-pilot one reason, and none for the items they do not hold', () => {
    const status = makeStatus({
      certificate: { type: 'none', number: '', ratings: [], verification: NOT_VERIFIED },
      medical: { type: 'none', expiration: null, is_current: false, verification: NOT_VERIFIED },
      photo_id: { type: 'not_provided', verification: NOT_VERIFIED },
      go_no_go: { membership: true, medical: false, verified: false },
    });
    expect(noGoReasons(status)).toEqual(['Not a pilot']);
  });

  it('gives a pilot with no medical one reason for it', () => {
    const status = makeStatus({
      medical: { type: 'none', expiration: null, is_current: false, verification: NOT_VERIFIED },
      go_no_go: { membership: true, medical: false, verified: false },
    });
    expect(noGoReasons(status)).toEqual(['No medical on file']);
  });

  it('gives a lapsed medical nobody verified one reason', () => {
    const status = makeStatus({
      medical: {
        type: 'third',
        expiration: '2025-02-02',
        is_current: false,
        verification: NOT_VERIFIED,
      },
      go_no_go: { membership: true, medical: false, verified: false },
    });
    expect(noGoReasons(status)).toEqual(['Medical expired']);
  });

  it('says a pilot with no photo ID on file has none, not that it is unverified', () => {
    const status = makeStatus({
      photo_id: { type: 'not_provided', verification: NOT_VERIFIED },
      go_no_go: { membership: true, medical: true, verified: false },
    });
    expect(noGoReasons(status)).toEqual(['No photo ID on file']);
  });

  it('is a no-go when membership and medical are current but an item is unverified', () => {
    const status = makeStatus({
      photo_id: { type: 'passport', verification: NOT_VERIFIED },
      go_no_go: { membership: true, medical: true, verified: false },
    });
    expect(isGo(status)).toBe(false);
  });
});

describe('MemberStatusCard', () => {
  it('shows a GO band when membership and medical are current and verified', () => {
    renderWithProviders(<MemberStatusCard userId={7} status={makeStatus()} today={TODAY} />);
    expect(screen.getByText('GO')).toBeInTheDocument();
    expect(screen.getByText('Membership and medical are current and verified')).toBeInTheDocument();
  });

  it('shows a NO-GO band and the reasons', () => {
    renderWithProviders(
      <MemberStatusCard
        userId={7}
        status={makeStatus({
          membership: { status: 'expired', expires_on: '2026-01-31', plan: 'Annual' },
          medical: {
            type: 'third',
            expiration: '2026-02-01',
            is_current: false,
            verification: VERIFIED_MEDICAL,
          },
          go_no_go: { membership: false, medical: false, verified: true },
        })}
        today={TODAY}
      />,
    );
    expect(screen.getByText('NO-GO')).toBeInTheDocument();
    expect(screen.getByText('Membership expired · Medical expired')).toBeInTheDocument();
  });

  it('names the member, their DART and how to reach them', () => {
    renderWithProviders(<MemberStatusCard userId={7} status={makeStatus()} today={TODAY} />);
    expect(screen.getByRole('heading', { name: 'Marta Reyes' })).toBeInTheDocument();
    expect(screen.getByText('Palo Alto DART', { exact: false })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '650-555-0100' })).toHaveAttribute(
      'href',
      'tel:6505550100',
    );
    expect(screen.getByRole('link', { name: 'marta@example.org' })).toHaveAttribute(
      'href',
      'mailto:marta@example.org',
    );
  });

  it('spells out the certificate, its number and the ratings', () => {
    renderWithProviders(<MemberStatusCard userId={7} status={makeStatus()} today={TODAY} />);
    const row = screen.getByText('Certificate').closest('.leader-row');
    expect(row).toHaveTextContent('Private · 3181234 · Instrument');
  });

  it('labels a friend "Friend" and invents neither a plan nor a lifetime', () => {
    renderWithProviders(
      <MemberStatusCard
        userId={7}
        status={makeStatus({
          membership: { status: 'friend', expires_on: null, plan: null },
          go_no_go: { membership: false, medical: true, verified: true },
        })}
        today={TODAY}
      />,
    );
    const row = screen.getByText('Membership').closest('.leader-row') as HTMLElement;
    expect(row).toHaveTextContent(/^MembershipFriend—$/);
  });

  it('shows a lifetime membership without inventing an expiry', () => {
    renderWithProviders(
      <MemberStatusCard
        userId={7}
        status={makeStatus({
          membership: { status: 'current', expires_on: null, plan: 'Life' },
        })}
        today={TODAY}
      />,
    );
    expect(screen.getByText(/Life · lifetime/)).toBeInTheDocument();
  });

  it('flags each aircraft with its own insurance state', () => {
    renderWithProviders(
      <MemberStatusCard
        userId={7}
        status={makeStatus({
          aircraft: [
            makeAircraft(),
            makeAircraft({
              id: 2,
              n_number: 'N9021K',
              insurance_is_current: false,
              insurance_expiration: '2026-01-01',
            }),
            makeAircraft({
              id: 3,
              n_number: 'N44BE',
              insurance_is_current: false,
              insurance_expiration: null,
            }),
            makeAircraft({
              id: 4,
              n_number: 'N33MM',
              insurance_is_current: true,
              insurance_expiration: '2026-06-20',
            }),
          ],
        })}
        today={TODAY}
      />,
    );

    const rows = screen.getAllByRole('listitem');
    expect(within(rows[0]!).getByText('Insured')).toBeInTheDocument();
    expect(within(rows[1]!).getByText('Insurance expired')).toBeInTheDocument();
    expect(within(rows[2]!).getByText('No insurance on file')).toBeInTheDocument();
    expect(within(rows[2]!).getByText('no policy on file')).toBeInTheDocument();
    expect(within(rows[3]!).getByText('Expiring soon')).toBeInTheDocument();
  });

  it('marks an aircraft the coverage policy excludes, with the reason', () => {
    const reason = "Not covered: helicopters are excluded by CalDART's policy";
    renderWithProviders(
      <MemberStatusCard
        userId={7}
        status={makeStatus({
          aircraft: [
            makeAircraft({ category: 'helicopter', coverage: { excluded: true, reason } }),
          ],
        })}
        today={TODAY}
      />,
    );

    const row = screen.getByRole('listitem');
    expect(within(row).getByText('Not covered')).toHaveAttribute('title', reason);
    expect(within(row).getByText(new RegExp(reason))).toBeInTheDocument();
  });

  it('says so when the member has no aircraft', () => {
    renderWithProviders(
      <MemberStatusCard userId={7} status={makeStatus({ aircraft: [] })} today={TODAY} />,
    );
    expect(screen.getByText(/No aircraft on this member's profile/)).toBeInTheDocument();
  });

  it('lines the no-aircraft note up with the Aircraft header, as an aircraft row', () => {
    renderWithProviders(
      <MemberStatusCard userId={7} status={makeStatus({ aircraft: [] })} today={TODAY} />,
    );
    expect(screen.getByText(/No aircraft on this member's profile/)).toHaveClass(
      'leader-aircraft__row',
    );
  });

  it('announces the verdict to assistive technology', () => {
    renderWithProviders(<MemberStatusCard userId={7} status={makeStatus()} today={TODAY} />);
    expect(screen.getByRole('status')).toHaveTextContent('GO');
  });

  it('marks the medical and the certificate with who verified them', () => {
    renderWithProviders(<MemberStatusCard userId={7} status={makeStatus()} today={TODAY} />);
    for (const label of ['Medical', 'Certificate']) {
      const row = screen.getByText(label, { selector: 'dt' }).closest('.leader-row');
      expect(row).toHaveTextContent(/Verified by Dana Leader on 05\/01\/2026$/);
    }
  });

  it('shows the kind of photo ID and its mark', () => {
    renderWithProviders(
      <MemberStatusCard
        userId={7}
        status={makeStatus({ photo_id: { type: 'drivers_license', verification: NOT_VERIFIED } })}
        today={TODAY}
      />,
    );
    const row = screen.getByText('Photo ID', { selector: 'dt' }).closest('.leader-row');
    expect(row).toHaveTextContent(/^Photo ID\s*Driver's license\s*Not verified$/);
  });

  it('says a verifier is one, beside their DART', () => {
    renderWithProviders(
      <MemberStatusCard userId={7} status={makeStatus({ is_verifier: true })} today={TODAY} />,
    );
    expect(screen.getByText(/Palo Alto DART · Verifier/)).toBeInTheDocument();
  });

  it('names every operational role the person holds', () => {
    const status = makeStatus({ is_dart_leader: true, is_verifier: true });
    renderWithProviders(<MemberStatusCard userId={7} status={status} today={TODAY} />);
    expect(screen.getByText(/Palo Alto DART · DART leader · Verifier/)).toBeInTheDocument();
  });

  it('says so when the person has no DART', () => {
    renderWithProviders(
      <MemberStatusCard userId={7} status={makeStatus({ dart: null })} today={TODAY} />,
    );
    expect(screen.getByText(/^No DART/)).toBeInTheDocument();
  });

  it('reads a current policy nobody verified as Not verified in amber, as the aircraft check does', () => {
    renderWithProviders(
      <MemberStatusCard
        userId={7}
        status={makeStatus({ aircraft: [makeAircraft({ insurance_verified: false })] })}
        today={TODAY}
      />,
    );
    const row = screen.getByRole('listitem');
    expect(within(row).getByText('Not verified').closest('[data-tone]')).toHaveAttribute(
      'data-tone',
      'expiring',
    );
    expect(within(row).queryByText('Insured')).not.toBeInTheDocument();
  });

  it('draws no mark beside items a non-pilot does not hold', () => {
    renderWithProviders(
      <MemberStatusCard
        userId={7}
        status={makeStatus({
          certificate: { type: 'none', number: '', ratings: [], verification: NOT_VERIFIED },
          medical: {
            type: 'none',
            expiration: null,
            is_current: false,
            verification: NOT_VERIFIED,
          },
          photo_id: { type: 'not_provided', verification: NOT_VERIFIED },
          go_no_go: { membership: true, medical: false, verified: false },
        })}
        today={TODAY}
      />,
    );
    const text = (label: string) =>
      screen.getByText(label, { selector: 'dt' }).closest('.leader-row')?.textContent;
    expect([text('Certificate'), text('Medical'), text('Photo ID')]).toEqual([
      'CertificateNot a pilot',
      'MedicalNone',
      'Photo IDNot provided',
    ]);
  });

  it('says Expired beside a lapsed medical, though somebody verified it', () => {
    renderWithProviders(
      <MemberStatusCard
        userId={7}
        status={makeStatus({
          medical: {
            type: 'basicmed',
            expiration: '2025-02-02',
            is_current: false,
            verification: VERIFIED_MEDICAL,
          },
          go_no_go: { membership: true, medical: false, verified: true },
        })}
        today={TODAY}
      />,
    );
    const row = screen.getByText('Medical', { selector: 'dt' }).closest('.leader-row');
    expect(row).toHaveTextContent(
      /^MedicalExpired\s*BasicMed · expires 02\/02\/2025\s*Verified by Dana Leader/,
    );
  });
});

describe('MemberStatusCard verification', () => {
  /** Render the card for a reader holding `roles`, once their roles have loaded. */
  async function renderAs(roles: RoleSlug[], status = makeStatus()) {
    server.use(signedInAs(makeUser({ id: 99, roles })));
    renderWithProviders(<MemberStatusCard userId={7} status={status} today={TODAY} />);
    // The roles arrive after the first paint; wait for them before reading the head.
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Marta Reyes' })).toBeVisible());
  }

  it.each([
    ['verifier'],
    ['dart_leader'],
    ['user_admin'],
    ['account_admin'],
    ['system_admin'],
  ] as const)('offers %s the Verify button', async (role) => {
    await renderAs(['member', role]);
    expect(await screen.findByRole('button', { name: 'Verify' })).toBeInTheDocument();
  });

  it('offers a plain member no Verify button', async () => {
    await renderAs(['member']);
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Verify' })).toBeNull());
  });

  it('opens the panel on Verify and saves all three items in one request', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    server.use(...verificationHandlers(calls));
    const unverified = makeStatus({
      certificate: { ...makeStatus().certificate, verification: NOT_VERIFIED },
      medical: { ...makeStatus().medical, verification: NOT_VERIFIED },
      photo_id: { type: 'passport', verification: NOT_VERIFIED },
      go_no_go: { membership: true, medical: true, verified: false },
    });
    await renderAs(['member', 'dart_leader'], unverified);

    await user.click(await screen.findByRole('button', { name: 'Verify' }));
    await user.click(screen.getByLabelText('Pilot certificate verified'));
    await user.click(screen.getByLabelText('Medical verified'));
    await user.click(screen.getByLabelText('Photo ID verified'));
    await user.click(screen.getByRole('button', { name: 'Save verification' }));

    expect(await screen.findByText('Verification saved')).toBeInTheDocument();
    expect(calls.members).toEqual([
      { userId: 7, body: { verified: ['certificate', 'medical', 'photo_id'] } },
    ]);
  });

  it.each([['dart_leader'], ['user_admin']] as const)(
    'lets %s make the person a verifier',
    async (role) => {
      const user = userEvent.setup();
      const calls = emptyVerificationCalls();
      server.use(...verificationHandlers(calls));
      await renderAs(['member', role]);

      await user.click(await screen.findByRole('button', { name: 'Make a verifier' }));
      await user.click(screen.getByRole('button', { name: 'Yes, make a verifier' }));

      expect(await screen.findByText('Marta Reyes is a verifier.')).toBeInTheDocument();
      expect(calls.verifier).toEqual([{ userId: 7, body: { verifier: true } }]);
    },
  );

  it('offers to remove a verifier', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    server.use(...verificationHandlers(calls));
    await renderAs(['member', 'dart_leader'], makeStatus({ is_verifier: true }));

    await user.click(await screen.findByRole('button', { name: 'Remove as verifier' }));
    await user.click(screen.getByRole('button', { name: 'Yes, remove as verifier' }));

    expect(await screen.findByText('Marta Reyes is no longer a verifier.')).toBeInTheDocument();
    expect(calls.verifier).toEqual([{ userId: 7, body: { verifier: false } }]);
  });

  it('asks before making somebody a verifier, starting on Cancel', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    server.use(...verificationHandlers(calls));
    await renderAs(['member', 'dart_leader']);

    await user.click(await screen.findByRole('button', { name: 'Make a verifier' }));

    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
    expect(calls.verifier).toEqual([]);
  });

  it('makes nobody a verifier when the question is cancelled', async () => {
    const user = userEvent.setup();
    const calls = emptyVerificationCalls();
    server.use(...verificationHandlers(calls));
    await renderAs(['member', 'dart_leader']);

    await user.click(await screen.findByRole('button', { name: 'Make a verifier' }));
    await user.keyboard('{Enter}');

    expect(screen.queryByRole('button', { name: 'Yes, make a verifier' })).toBeNull();
    expect(calls.verifier).toEqual([]);
  });

  it.each([['verifier'], ['account_admin']] as const)(
    'offers %s no verifier button',
    async (role) => {
      await renderAs(['member', role]);
      await screen.findByRole('button', { name: 'Verify' });
      expect(screen.queryByRole('button', { name: 'Make a verifier' })).toBeNull();
    },
  );
});
