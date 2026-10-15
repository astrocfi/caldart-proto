import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { RenewalSettleResult } from '@/portal/api/types';
import { renderWithProviders, signedInClient } from '@test/render';
import { ClosedChargeNotice } from './ClosedChargeNotice';

const CLOSED: RenewalSettleResult = {
  id: 88,
  mandate_id: 13,
  mandate_kind: 'renewal',
  membership_id: 455,
  payment_id: 901,
  user_id: 35,
  user_name: 'Ben Ortiz',
  scheduled_on: '2026-03-15',
  outcome: 'failed',
  error: 'Closed by the treasurer after checking with the provider.',
  noticed_at: '2026-03-01T06:30:11Z',
  attempted_at: null,
  in_doubt: false,
  flagged_at: null,
  payment_amount_cents: 4500,
  payment_sent_at: '2026-03-15T13:30:00Z',
  result_emailed_at: null,
  created_at: '2026-03-01T06:30:11Z',
  user_email: 'ben@example.org',
  user_phone: '415-555-0142',
  member_emailed: true,
};

function renderNotice(result: RenewalSettleResult, client = signedInClient('treasurer')): void {
  const handleDismiss = vi.fn();
  renderWithProviders(<ClosedChargeNotice result={result} onDismiss={handleDismiss} />, { client });
}

/** The notice's words, every run of whitespace a single space. */
function noticeText(): string {
  return (screen.getByRole('status').textContent ?? '').replace(/\s+/g, ' ').trim();
}

describe('ClosedChargeNotice', () => {
  it('says the member is emailed that their automatic renewal is paused', () => {
    renderNotice(CLOSED);

    expect(noticeText()).toContain(
      'The charge for Ben Ortiz is closed and their automatic renewal is paused. They are emailed that it is paused.',
    );
  });

  it('asks the treasurer to call or write, naming the phone and the address', () => {
    renderNotice(CLOSED);

    expect(noticeText()).toContain(
      'Please get in touch with them too: call 415-555-0142 or write to ben@example.org.',
    );
  });

  it('links the phone number for a call', () => {
    renderNotice(CLOSED);

    expect(screen.getByRole('link', { name: '415-555-0142' })).toHaveAttribute(
      'href',
      'tel:415-555-0142',
    );
  });

  it('links the address for an email', () => {
    renderNotice(CLOSED);

    expect(screen.getByRole('link', { name: 'ben@example.org' })).toHaveAttribute(
      'href',
      'mailto:ben@example.org',
    );
  });

  it('names the address alone for a member without a phone number', () => {
    renderNotice({ ...CLOSED, user_phone: '' });

    expect(noticeText()).toContain('Please get in touch with them too: write to ben@example.org.');
  });

  it('names a recurring donation by its kind', () => {
    renderNotice({ ...CLOSED, mandate_kind: 'contribution', membership_id: null });

    expect(noticeText()).toContain('their recurring donation is paused');
  });

  it('says the member isn’t emailed when the close didn’t email them', () => {
    renderNotice({ ...CLOSED, member_emailed: false });

    expect(noticeText()).toContain(
      'The charge for Ben Ortiz is closed, and they aren’t emailed about it. Please get in touch with them: call',
    );
  });

  it("links the member's money history", () => {
    renderNotice(CLOSED);

    expect(screen.getByRole('link', { name: 'Ben Ortiz’s money history' })).toHaveAttribute(
      'href',
      '/admin/payments/members/35',
    );
  });

  it('links the member record for an account administrator', () => {
    renderNotice(CLOSED, signedInClient('account_admin'));

    expect(screen.getByRole('link', { name: 'Member record' })).toHaveAttribute(
      'href',
      '/admin/members/35',
    );
  });

  it('doesn’t offer a treasurer the member record', () => {
    renderNotice(CLOSED);

    expect(screen.queryByRole('link', { name: 'Member record' })).not.toBeInTheDocument();
  });

  it('is dismissed with Dismiss', async () => {
    const handleDismiss = vi.fn();
    renderWithProviders(<ClosedChargeNotice result={CLOSED} onDismiss={handleDismiss} />, {
      client: signedInClient('treasurer'),
    });

    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }));

    expect(handleDismiss).toHaveBeenCalledOnce();
  });
});
