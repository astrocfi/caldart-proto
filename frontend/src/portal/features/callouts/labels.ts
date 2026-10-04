/** The words the Callouts screens use for an answer and for a callout's state. */
import type { CalloutAnswerKind, CalloutSummary } from '@/portal/api/types';
import { formatDateAt } from '@/portal/components/DateText';
import type { StatusTone } from '@/portal/components/StatusChip';
import { SITE_TIME_ZONE } from '@/portal/features/bulk-email/schedule';

/** Each answer as the email's buttons word it. */
export const ANSWER_LABELS: Record<CalloutAnswerKind, string> = {
  available: 'Available',
  limited: 'Available with limits',
  unavailable: 'Not available',
};

/** The tone of each answer's dot, and of no answer. */
export function answerTone(answer: CalloutAnswerKind | null): StatusTone {
  if (answer === 'available') return 'current';
  if (answer === 'limited') return 'expiring';
  if (answer === 'unavailable') return 'expired';
  return 'none';
}

/** An answer in words, `No answer yet` before one is given. */
export function answerLabel(answer: CalloutAnswerKind | null): string {
  return answer === null ? 'No answer yet' : ANSWER_LABELS[answer];
}

/**
 * Whether a callout takes answers, and until when, in the site's time zone:
 * `Taking answers until 10/05/2026 at 8:00 PM`, or `Closed 10/04/2026 at 9:15 AM`.
 */
export function openLabel(callout: CalloutSummary): string {
  if (callout.is_open) {
    return `Taking answers until ${formatDateAt(callout.closes_at, SITE_TIME_ZONE)}`;
  }
  return `Closed ${formatDateAt(callout.closed_at ?? callout.closes_at, SITE_TIME_ZONE)}`;
}
