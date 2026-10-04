/** The words the Callouts screens use for an answer and for a callout's state. */
import type { CalloutAnswerKind, CalloutSummary } from '@/portal/api/types';
import type { StatusTone } from '@/portal/components/StatusChip';

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

/** Whether a callout takes answers, in words. */
export function openLabel(callout: CalloutSummary): string {
  return callout.is_open ? 'Taking answers' : 'Closed';
}
