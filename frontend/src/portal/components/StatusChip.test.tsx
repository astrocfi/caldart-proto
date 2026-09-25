import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { MembershipStatus } from '../api/types';
import { CurrencyChip, MembershipChip, StatusChip, daysUntil, membershipTone } from './StatusChip';

const TODAY = new Date(2026, 5, 15); // 15 June 2026, local time

function membership(overrides: Partial<MembershipStatus> = {}): MembershipStatus {
  return {
    status: 'current',
    expires_on: '2027-06-30',
    plan: 'Annual',
    is_lifetime: false,
    ...overrides,
  };
}

describe('daysUntil', () => {
  it('counts whole days ahead', () => {
    expect(daysUntil('2026-06-20', TODAY)).toBe(5);
  });

  it('is zero on the day itself', () => {
    expect(daysUntil('2026-06-15', TODAY)).toBe(0);
  });

  it('goes negative in the past', () => {
    expect(daysUntil('2026-06-01', TODAY)).toBe(-14);
  });

  it('returns null for no date or a bad date', () => {
    expect(daysUntil(null, TODAY)).toBeNull();
    expect(daysUntil('not-a-date', TODAY)).toBeNull();
  });
});

describe('membershipTone', () => {
  it('is `none` when there is no membership', () => {
    expect(membershipTone(membership({ status: 'none', expires_on: null }), TODAY)).toBe('none');
  });

  it('is `expired` for a lapsed membership', () => {
    expect(membershipTone(membership({ status: 'expired', expires_on: '2026-01-01' }), TODAY)).toBe(
      'expired',
    );
  });

  it('is `current` when expiry is comfortably away', () => {
    expect(membershipTone(membership({ expires_on: '2026-12-31' }), TODAY)).toBe('current');
  });

  it('is `expiring` inside the 30-day window', () => {
    expect(membershipTone(membership({ expires_on: '2026-07-01' }), TODAY)).toBe('expiring');
    expect(membershipTone(membership({ expires_on: '2026-07-15' }), TODAY)).toBe('expiring');
  });

  it('is `current` one day outside the window', () => {
    expect(membershipTone(membership({ expires_on: '2026-07-16' }), TODAY)).toBe('current');
  });

  it('treats lifetime as current, never expiring', () => {
    expect(membershipTone(membership({ expires_on: null, is_lifetime: true }), TODAY)).toBe(
      'current',
    );
  });
});

describe('StatusChip', () => {
  it('renders the default label and tone class', () => {
    render(<StatusChip tone="expired" />);
    const chip = screen.getByText('Expired');
    expect(chip).toHaveClass('chip', 'chip--bad');
    expect(chip).toHaveAttribute('data-tone', 'expired');
  });

  it('accepts an override label', () => {
    render(<StatusChip tone="current" label="Insured" />);
    expect(screen.getByText('Insured')).toHaveClass('chip--ok');
  });

  it('labels the `new` tone "Unpaid", the same word the member report uses', () => {
    render(<StatusChip tone="new" />);
    expect(screen.getByText('Unpaid')).toHaveClass('chip--info');
  });

  it('labels the `none` tone "No membership", the same word the member report uses', () => {
    render(<StatusChip tone="none" />);
    expect(screen.getByText('No membership')).toHaveClass('chip--neutral');
  });
});

describe('MembershipChip', () => {
  it('says "Never expires" for lifetime members', () => {
    render(
      <MembershipChip
        membership={membership({ expires_on: null, is_lifetime: true })}
        today={TODAY}
      />,
    );
    expect(screen.getByText('Never expires')).toBeInTheDocument();
  });

  it('warns when the membership is expiring', () => {
    render(<MembershipChip membership={membership({ expires_on: '2026-07-01' })} today={TODAY} />);
    expect(screen.getByText('Expiring soon')).toHaveClass('chip--warn');
  });
});

describe('CurrencyChip', () => {
  it('distinguishes current, expired, and missing', () => {
    const { rerender } = render(<CurrencyChip isCurrent />);
    expect(screen.getByText('Current')).toHaveClass('chip--ok');

    rerender(<CurrencyChip isCurrent={false} />);
    expect(screen.getByText('Expired')).toHaveClass('chip--bad');

    rerender(<CurrencyChip isCurrent={false} missing />);
    expect(screen.getByText('Not on file')).toHaveClass('chip--neutral');
  });
});
