import { describe, expect, it } from 'vitest';

import { runSummary, skippedBreakdown } from './runSummary';

const REASON_LABELS: Record<string, string> = {
  already_sent: 'already sent',
  auto_renew: 'auto-renew on',
  lifetime: 'lifetime member',
};

describe('runSummary', () => {
  it('says what a dry run would have done', () => {
    expect(runSummary({ sent: 3, skipped: 1 }, true)).toBe('Would send 3 emails, skipped 1.');
  });

  it('says what a real run did, in the singular', () => {
    expect(runSummary({ sent: 1, skipped: 0 }, false)).toBe('Sent 1 email, skipped 0.');
  });
});

describe('skippedBreakdown', () => {
  it('lists every reason with a count above zero, in the order the labels give them', () => {
    expect(skippedBreakdown({ already_sent: 10, auto_renew: 2 }, REASON_LABELS)).toBe(
      'Skipped: already sent 10, auto-renew on 2.',
    );
  });

  it('says nothing when every reason is at zero', () => {
    expect(skippedBreakdown({}, REASON_LABELS)).toBe('');
  });

  it('omits a reason present in the payload at zero', () => {
    expect(skippedBreakdown({ already_sent: 0, lifetime: 3 }, REASON_LABELS)).toBe(
      'Skipped: lifetime member 3.',
    );
  });

  it('appends a reason it has no label for by its raw slug, rather than dropping it', () => {
    expect(skippedBreakdown({ already_sent: 10, future_reason: 3 }, REASON_LABELS)).toBe(
      'Skipped: already sent 10, future_reason 3.',
    );
  });
});
