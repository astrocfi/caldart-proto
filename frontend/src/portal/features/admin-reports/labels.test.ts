import { describe, expect, it } from 'vitest';

import { makeSubscription } from '@test/handlers';
import { recipientLabel, reportKindLabel, reportSkippedBreakdown, scheduleLabel } from './labels';

describe('scheduleLabel', () => {
  it('names the weekday of a weekly schedule', () => {
    expect(scheduleLabel('weekly', 0)).toBe('Weekly on Monday');
  });

  it('names Sunday as the seventh day', () => {
    expect(scheduleLabel('weekly', 6)).toBe('Weekly on Sunday');
  });

  it.each([
    ['monthly', 'Monthly'],
    ['quarterly', 'Quarterly'],
    ['yearly', 'Yearly'],
  ] as const)('reads %s as %s, whatever the weekday', (cadence, label) => {
    expect(scheduleLabel(cadence, 3)).toBe(label);
  });
});

describe('recipientLabel', () => {
  it('names the bound account', () => {
    expect(recipientLabel(makeSubscription({ recipient_name: 'Ada Admin' }))).toBe('Ada Admin');
  });

  it('falls back to the address outside CalDART', () => {
    const subscription = makeSubscription({
      recipient_user: null,
      recipient_name: '',
      recipient_email: 'board@example.org',
    });
    expect(recipientLabel(subscription)).toBe('board@example.org');
  });
});

describe('reportKindLabel', () => {
  it.each([
    ['report', 'Report'],
    ['roster', 'Roster'],
  ])('reads %s as %s', (kind, label) => {
    expect(reportKindLabel(kind)).toBe(label);
  });

  it('keeps a kind it does not know by its slug', () => {
    expect(reportKindLabel('digest')).toBe('digest');
  });
});

describe('reportSkippedBreakdown', () => {
  it('names each reason in words', () => {
    expect(reportSkippedBreakdown({ no_recipients: 2, no_email: 1, not_permitted: 1 })).toBe(
      'Skipped: no longer permitted 1, nobody ticked 2, no address on file 1.',
    );
  });

  it('is empty when nothing was skipped', () => {
    expect(reportSkippedBreakdown({})).toBe('');
  });
});
