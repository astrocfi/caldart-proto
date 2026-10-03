import { describe, expect, it } from 'vitest';

import type { BulkEmailDetail } from '@/portal/api/types';
import {
  addSentence,
  batchSentence,
  progressSentence,
  resultSentence,
  statusLabel,
  timeLeft,
} from './status';
import { makeBulkEmail } from '@test/fixtures/bulkEmail';

describe('statusLabel', () => {
  it('reads a scheduled email as Scheduled', () => {
    expect(statusLabel({ status: 'queued', scheduled: true, started_at: null })).toBe('Scheduled');
  });

  it('reads an email in its undo window as Waiting to send', () => {
    expect(statusLabel({ status: 'queued', scheduled: false, started_at: null })).toBe(
      'Waiting to send',
    );
  });

  it('reads an email queued again by Send the rest as waiting to send the rest', () => {
    expect(
      statusLabel({ status: 'queued', scheduled: false, started_at: '2026-04-06T17:00:00Z' }),
    ).toBe('Waiting to send the rest');
  });
});

describe('the counting sentences', () => {
  it('counts who receives the email and who is skipped', () => {
    expect(batchSentence(38, 4)).toBe('38 people will receive this email; 4 are skipped.');
  });

  it('speaks of one person in the singular', () => {
    expect(batchSentence(1, 1)).toBe('1 person will receive this email; 1 is skipped.');
  });

  it('leaves out a count of nobody already there', () => {
    expect(addSentence({ added: 12, already_present: 0, count: 12 })).toBe('Added 12 people.');
  });

  it('says what an add did', () => {
    expect(addSentence({ added: 12, already_present: 3, count: 41 })).toBe(
      'Added 12 people; 3 were already in the batch.',
    );
  });
});

describe('timeLeft', () => {
  const now = new Date('2026-04-06T17:00:00Z');

  it('rounds to whole minutes', () => {
    expect(timeLeft('2026-04-06T17:03:10Z', now)).toBe('about 3 minutes');
  });

  it('says less than a minute near the end', () => {
    expect(timeLeft('2026-04-06T17:00:20Z', now)).toBe('less than a minute');
  });
});

describe('progressSentence', () => {
  it('counts what has gone out of the whole and the time left', () => {
    const email: BulkEmailDetail = makeBulkEmail({
      status: 'sending',
      sent_count: 12,
      failed_count: 0,
      remaining: 26,
      estimated_finish_at: '2026-04-06T17:01:00Z',
    });
    expect(progressSentence(email, new Date('2026-04-06T17:00:00Z'))).toBe(
      'Sending… 12 of 38 sent, about 1 minute left.',
    );
  });
});

describe('resultSentence', () => {
  it('counts a finished send', () => {
    expect(
      resultSentence({ status: 'sent', sent_count: 37, failed_count: 1, skipped_count: 4 }),
    ).toBe('Sent to 37 people. 1 failed and 4 were skipped.');
  });

  it('says everyone was sent a copy when nothing failed or was skipped', () => {
    expect(
      resultSentence({ status: 'sent', sent_count: 51, failed_count: 0, skipped_count: 0 }),
    ).toBe('Sent to 51 people. Everyone was sent a copy.');
  });

  it('names who stopped a stopped send', () => {
    expect(
      resultSentence({
        status: 'stopped',
        sent_count: 12,
        failed_count: 0,
        skipped_count: 1,
        stopped_by: 'Grace Holloway',
      }),
    ).toBe('Stopped by Grace Holloway. Sent to 12 people. 0 failed and 1 was skipped.');
  });
});
