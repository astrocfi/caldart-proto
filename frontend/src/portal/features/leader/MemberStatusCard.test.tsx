import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@test/render';
import type { AircraftSummary, LeaderStatus } from '@/portal/api/types';
import { MemberStatusCard, isGo, noGoReasons } from './MemberStatusCard';

const TODAY = new Date('2026-06-01T09:00:00');

function makeAircraft(overrides: Partial<AircraftSummary> = {}): AircraftSummary {
  return {
    id: 1,
    n_number: 'N172SP',
    make: 'Cessna',
    model: '172S Skyhawk',
    insurance_is_current: true,
    insurance_expiration: '2027-03-01',
    insurance_summary: '$1,000,000 / $100,000 · exp 2027-03-01',
    ...overrides,
  };
}

function makeStatus(overrides: Partial<LeaderStatus> = {}): LeaderStatus {
  return {
    name: 'Marta Reyes',
    email: 'marta@example.org',
    phone: '650-555-0100',
    dart: 'Palo Alto',
    membership: { status: 'current', expires_on: '2027-06-30', plan: 'Annual' },
    certificate: { type: 'private', number: '3181234', ifr_rated: 'yes', ratings: ['instrument'] },
    medical: { type: 'third', expiration: '2026-12-01', is_current: true },
    aircraft: [makeAircraft()],
    go_no_go: { membership: true, medical: true },
    ...overrides,
  };
}

describe('isGo / noGoReasons', () => {
  it.each([
    [true, true, true, []],
    [false, true, false, ['Membership expired']],
    [true, false, false, ['Medical expired']],
    [false, false, false, ['Membership expired', 'Medical expired']],
  ])('membership=%s medical=%s -> go=%s', (membership, medical, expectedGo, expectedReasons) => {
    const status = makeStatus({
      membership: { status: membership ? 'current' : 'expired', expires_on: null, plan: 'Annual' },
      medical: { type: 'third', expiration: '2020-01-01', is_current: medical },
      go_no_go: { membership, medical },
    });
    expect(isGo(status)).toBe(expectedGo);
    expect(noGoReasons(status)).toEqual(expectedReasons);
  });

  it('says "never joined" rather than "expired" when there is no membership', () => {
    const status = makeStatus({
      membership: { status: 'none', expires_on: null, plan: null },
      go_no_go: { membership: false, medical: true },
    });
    expect(noGoReasons(status)).toEqual(['No CalDART membership']);
  });

  it('does not call a medical expired when no expiry was ever entered', () => {
    const status = makeStatus({
      medical: { type: 'third', expiration: null, is_current: false },
      go_no_go: { membership: true, medical: false },
    });
    expect(noGoReasons(status)).toEqual(['No medical expiry on file']);
  });

  it('says "no medical on file" when none was ever entered', () => {
    const status = makeStatus({
      medical: { type: 'none', expiration: null, is_current: false },
      go_no_go: { membership: true, medical: false },
    });
    expect(noGoReasons(status)).toEqual(['No medical on file']);
  });
});

describe('MemberStatusCard', () => {
  it('shows a GO band when membership and medical are current', () => {
    renderWithProviders(<MemberStatusCard status={makeStatus()} today={TODAY} />);
    expect(screen.getByText('GO')).toBeInTheDocument();
    expect(screen.getByText(/Membership and medical are current/)).toBeInTheDocument();
  });

  it('shows a NO-GO band and the reasons', () => {
    renderWithProviders(
      <MemberStatusCard
        status={makeStatus({
          membership: { status: 'expired', expires_on: '2026-01-31', plan: 'Annual' },
          medical: { type: 'third', expiration: '2026-02-01', is_current: false },
          go_no_go: { membership: false, medical: false },
        })}
        today={TODAY}
      />,
    );
    expect(screen.getByText('NO-GO')).toBeInTheDocument();
    expect(screen.getByText('Membership expired · Medical expired')).toBeInTheDocument();
  });

  it('names the member, their DART and how to reach them', () => {
    renderWithProviders(<MemberStatusCard status={makeStatus()} today={TODAY} />);
    expect(screen.getByRole('heading', { name: 'Marta Reyes' })).toBeInTheDocument();
    expect(screen.getByText('Palo Alto', { exact: false })).toBeInTheDocument();
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
    renderWithProviders(<MemberStatusCard status={makeStatus()} today={TODAY} />);
    const row = screen.getByText('Certificate').closest('.leader-row');
    expect(row).toHaveTextContent('Private · 3181234 · IFR · Instrument');
  });

  it('shows a lifetime membership without inventing an expiry', () => {
    renderWithProviders(
      <MemberStatusCard
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

  it('says so when the member has no aircraft', () => {
    renderWithProviders(<MemberStatusCard status={makeStatus({ aircraft: [] })} today={TODAY} />);
    expect(screen.getByText(/No aircraft on this member's profile/)).toBeInTheDocument();
  });

  it('lines the no-aircraft note up with the Aircraft header, as an aircraft row', () => {
    renderWithProviders(<MemberStatusCard status={makeStatus({ aircraft: [] })} today={TODAY} />);
    expect(screen.getByText(/No aircraft on this member's profile/)).toHaveClass(
      'leader-aircraft__row',
    );
  });

  it('announces the verdict to assistive technology', () => {
    renderWithProviders(<MemberStatusCard status={makeStatus()} today={TODAY} />);
    expect(screen.getByRole('status')).toHaveTextContent('GO');
  });
});
