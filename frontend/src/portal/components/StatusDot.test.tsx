import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { MembershipStatus } from '../api/types';
import { CurrencyDot, MembershipDot, StatusDot, daysUntil, membershipTone } from './StatusDot';

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
  it.each([
    ['current', 'current'],
    ['expired', 'expired'],
    ['friend', 'none'],
    ['donor', 'none'],
  ] as const)('gives a `%s` membership with no end date the `%s` tone', (status, tone) => {
    expect(membershipTone(membership({ status, expires_on: null }), TODAY)).toBe(tone);
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

describe('StatusDot', () => {
  it('shows its word as visible text', () => {
    render(<StatusDot tone="expired" />);
    expect(screen.getByText('Expired')).not.toHaveClass('visually-hidden');
  });

  it('carries its tone on the word', () => {
    render(<StatusDot tone="expired" />);
    expect(screen.getByText('Expired')).toHaveAttribute('data-tone', 'expired');
  });

  it('hides the dot from a screen reader, since the word says it', () => {
    const { container } = render(<StatusDot tone="current" label="Insured" />);
    expect(container.querySelector('.status-dot')).toHaveAttribute('aria-hidden', 'true');
  });

  it('colors the dot by its tone', () => {
    const { container } = render(<StatusDot tone="expiring" label="Pending" />);
    expect(container.querySelector('.status-dot')).toHaveAttribute('data-tone', 'expiring');
  });

  it('accepts an override label', () => {
    render(<StatusDot tone="current" label="Insured" />);
    expect(screen.getByText('Insured')).toHaveAttribute('data-tone', 'current');
  });

  it('labels the `none` tone "Friend", the same word the member report uses', () => {
    render(<StatusDot tone="none" />);
    expect(screen.getByText('Friend')).toHaveAttribute('data-tone', 'none');
  });

  it('is never drawn as a chip', () => {
    const { container } = render(<StatusDot tone="current" />);
    expect(container.querySelector('.chip')).toBeNull();
  });

  it('keeps a hidden word for a screen reader beside a value that says it', () => {
    render(<StatusDot tone="expired" label="Insurance expired" hideWord />);
    expect(screen.getByText('Insurance expired')).toHaveClass('visually-hidden');
  });

  it('shows a hidden word on hover', () => {
    render(<StatusDot tone="expired" label="Insurance expired" hideWord />);
    expect(screen.getByTitle('Insurance expired')).toHaveAttribute('data-tone', 'expired');
  });
});

describe('MembershipDot', () => {
  it('says "Never expires" for lifetime members', () => {
    render(
      <MembershipDot
        membership={membership({ expires_on: null, is_lifetime: true })}
        today={TODAY}
      />,
    );
    expect(screen.getByText('Never expires')).toBeInTheDocument();
  });

  it('warns when the membership is expiring', () => {
    render(<MembershipDot membership={membership({ expires_on: '2026-07-01' })} today={TODAY} />);
    expect(screen.getByText('Expiring soon')).toHaveAttribute('data-tone', 'expiring');
  });

  it('shows the date the membership runs to on hover', () => {
    render(<MembershipDot membership={membership({ expires_on: '2026-07-01' })} today={TODAY} />);
    expect(screen.getByText('Expiring soon')).toHaveAttribute('title', 'Runs to 07/01/2026');
  });
});

describe('CurrencyDot', () => {
  it.each([
    [{ isCurrent: true }, 'Current', 'current'],
    [{ isCurrent: false }, 'Expired', 'expired'],
    [{ isCurrent: false, missing: true }, 'Not on file', 'none'],
  ])('reads %o as %s', (props, word, tone) => {
    render(<CurrencyDot {...props} />);
    expect(screen.getByText(word)).toHaveAttribute('data-tone', tone);
  });
});

describe('a friend of CalDART', () => {
  const FRIEND = membership({ status: 'friend', expires_on: null, plan: null });

  it('takes the quiet `none` tone, never current or expired', () => {
    expect(membershipTone(FRIEND, TODAY)).toBe('none');
  });

  it('reads Friend beside the gray dot', () => {
    render(<MembershipDot membership={FRIEND} today={TODAY} />);
    expect(screen.getByText('Friend')).toHaveAttribute('data-tone', 'none');
  });
});
