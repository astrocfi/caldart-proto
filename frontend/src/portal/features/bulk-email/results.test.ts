import { describe, expect, it } from 'vitest';

import type { BulkEmailDetail, BulkEmailPreview } from '@/portal/api/types';
import {
  peopleCaption,
  previewActions,
  previewSummary,
  resultLabel,
  sendLabel,
  sentSummary,
} from './results';

const PREVIEW: BulkEmailPreview = {
  count: 1,
  skipped_count: 1,
  recipients: [{ user_id: 1, name: 'Ann Able', email: 'ann@example.org', reason: '' }],
  skipped: [
    { user_id: 2, name: 'Gil Gone', email: 'gil@example.org', reason: 'Account deactivated' },
  ],
};

describe('previewActions', () => {
  it('lists the people to send to, then the skips with their reasons', () => {
    expect(previewActions(PREVIEW).map((row) => [row.kind, row.member, row.detail])).toEqual([
      ['to_send', 'Ann Able', ''],
      ['skipped', 'Gil Gone', 'Account deactivated'],
    ]);
  });
});

describe('resultLabel', () => {
  it.each([
    ['to_send', 'To send'],
    ['pending', 'Not sent'],
    ['sent', 'Sent'],
    ['failed', 'Failed'],
    ['skipped', 'Skipped'],
    ['bounced', 'bounced'],
  ])('reads %s as %s', (kind, label) => {
    expect(resultLabel(kind)).toBe(label);
  });
});

describe('previewSummary', () => {
  it('counts one person and one skip in the singular', () => {
    expect(previewSummary(PREVIEW)).toBe('1 person will be sent this email; 1 is skipped.');
  });

  it('counts several in the plural', () => {
    expect(previewSummary({ ...PREVIEW, count: 3, skipped_count: 0 })).toBe(
      '3 people will be sent this email; 0 are skipped.',
    );
  });
});

describe('sendLabel', () => {
  it.each([
    [1, 'Send to 1 person'],
    [40, 'Send to 40 people'],
  ])('names %i as %s', (count, label) => {
    expect(sendLabel(count)).toBe(label);
  });
});

const SENT: BulkEmailDetail = {
  id: 7,
  subject: 'Spring seminar',
  body: 'Join us.',
  filters: {},
  sender: 'Grace Holloway',
  created_at: '2026-10-02T17:00:00Z',
  sent_at: '2026-10-02T17:00:05Z',
  sent_count: 1,
  failed_count: 0,
  skipped_count: 0,
  recipients: [
    { user_id: 1, name: 'Ann Able', email: 'ann@example.org', status: 'sent', reason: '' },
    { user_id: 2, name: 'Bea Bell', email: 'bea@example.org', status: 'pending', reason: '' },
  ],
};

describe('sentSummary', () => {
  it('counts a finished send', () => {
    expect(sentSummary(SENT)).toBe('Sent 1, failed 0, skipped 0.');
  });

  it('says an unfinished send was interrupted and counts the copies never sent', () => {
    expect(sentSummary({ ...SENT, sent_at: null })).toBe(
      'Interrupted: Sent 1, failed 0, skipped 0. Not sent 1.',
    );
  });
});

describe('peopleCaption', () => {
  it.each([
    [1, '1 person'],
    [0, '0 people'],
    [3, '3 people'],
  ])('captions %i as %s', (count, caption) => {
    expect(peopleCaption(count)).toBe(caption);
  });
});
