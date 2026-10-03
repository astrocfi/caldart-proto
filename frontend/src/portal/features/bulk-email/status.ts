/**
 * A bulk email's state, and each copy's, in the words and colors the screens use,
 * with the sentences that count people.
 */
import type {
  BulkEmailAddResult,
  BulkEmailDetail,
  BulkEmailRecipientStatus,
  BulkEmailStatus,
  BulkEmailSummary,
} from '@/portal/api/types';
import type { StatusTone } from '@/portal/components/StatusChip';

/** What each email status reads as; a queued email the sender scheduled reads *Scheduled*. */
const STATUS_LABELS: Record<BulkEmailStatus, string> = {
  draft: 'Draft',
  queued: 'Waiting to send',
  sending: 'Sending',
  sent: 'Sent',
  stopped: 'Stopped',
};

/** The dot beside each email status. */
const STATUS_TONES: Record<BulkEmailStatus, StatusTone> = {
  draft: 'none',
  queued: 'new',
  sending: 'expiring',
  sent: 'current',
  stopped: 'expired',
};

/** What each copy's status reads as. */
const RESULT_LABELS: Record<BulkEmailRecipientStatus, string> = {
  batched: 'In the batch',
  pending: 'Not sent yet',
  sent: 'Sent',
  failed: 'Failed',
  skipped: 'Skipped',
  stopped: 'Not sent (stopped)',
  bounced: 'Bounced',
};

/** The dot beside each copy's status. */
const RESULT_TONES: Record<BulkEmailRecipientStatus, StatusTone> = {
  batched: 'none',
  pending: 'new',
  sent: 'current',
  failed: 'expired',
  skipped: 'none',
  stopped: 'expiring',
  bounced: 'expired',
};

/** What a person's kind reads as. */
const KIND_LABELS: Record<string, string> = { member: 'Member', friend: 'Friend' };

/**
 * An email's status in words: a queued email the sender scheduled is *Scheduled*,
 * and one queued again by Send the rest is *Waiting to send the rest*.
 */
export function statusLabel(
  email: Pick<BulkEmailSummary, 'status' | 'scheduled' | 'started_at'>,
): string {
  if (email.status === 'queued' && email.started_at !== null) return 'Waiting to send the rest';
  if (email.status === 'queued' && email.scheduled) return 'Scheduled';
  return STATUS_LABELS[email.status];
}

/** The dot's tone for an email's status. */
export function statusTone(status: BulkEmailStatus): StatusTone {
  return STATUS_TONES[status];
}

/** A copy's status in words. */
export function resultLabel(status: BulkEmailRecipientStatus): string {
  return RESULT_LABELS[status];
}

/** The dot's tone for a copy's status. */
export function resultTone(status: BulkEmailRecipientStatus): StatusTone {
  return RESULT_TONES[status];
}

/** A person's kind in words, or the kind itself for one this screen does not know. */
export function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

/** `1 person` or `12 people`. */
export function people(count: number): string {
  return count === 1 ? '1 person' : `${count} people`;
}

/** `38 people will receive this email; 4 are skipped.`: what the batch comes to. */
export function batchSentence(receiving: number, skipped: number): string {
  const skips = skipped === 1 ? '1 is skipped' : `${skipped} are skipped`;
  return `${people(receiving)} will receive this email; ${skips}.`;
}

/**
 * `Added 12 people; 3 were already in the batch.`: what one add did.  With nobody
 * there already it is `Added 12 people.`
 */
export function addSentence(result: BulkEmailAddResult): string {
  if (result.already_present === 0) return `Added ${people(result.added)}.`;
  const already =
    result.already_present === 1
      ? '1 was already in the batch'
      : `${result.already_present} were already in the batch`;
  return `Added ${people(result.added)}; ${already}.`;
}

/** `Send to 38 people`: the Send button's words. */
export function sendLabel(count: number): string {
  return `Send to ${people(count)}`;
}

/**
 * `about 3 minutes`: how long until `iso`, rounded to whole minutes, or `less than
 * a minute`.
 */
export function timeLeft(iso: string | null, now: Date = new Date()): string {
  if (iso === null) return 'less than a minute';
  const minutes = Math.round((new Date(iso).getTime() - now.getTime()) / 60_000);
  if (minutes < 1) return 'less than a minute';
  return minutes === 1 ? 'about 1 minute' : `about ${minutes} minutes`;
}

/**
 * How many copies the mail server took: those still counted sent, and those that went
 * and came back later, which the server counts as bounced instead.
 */
export function wentCount(
  email: Pick<BulkEmailDetail, 'sent_count'> & { bounced_count?: number },
): number {
  return email.sent_count + (email.bounced_count ?? 0);
}

/** `Sending… 12 of 38 sent, about 1 minute left.`: a send in progress. */
export function progressSentence(email: BulkEmailDetail, now: Date = new Date()): string {
  const went = wentCount(email);
  const total = went + email.failed_count + email.remaining;
  return `Sending… ${went} of ${total} sent, ${timeLeft(email.estimated_finish_at, now)} left.`;
}

/**
 * `Sent to 37 people. 1 failed and 4 were skipped.`: what a finished or stopped
 * send came to.  With nothing failed or skipped it is `Sent to 51 people. Everyone
 * was sent a copy.`  Copies that came back undelivered later are counted as sent and
 * then named: `2 came back undelivered.`
 */
export function resultSentence(
  email: Pick<BulkEmailDetail, 'status' | 'sent_count' | 'failed_count' | 'skipped_count'> & {
    stopped_by?: string;
    bounced_count?: number;
  },
): string {
  const bounced = email.bounced_count ?? 0;
  const returned = bounced === 0 ? '' : ` ${bounced} came back undelivered.`;
  const sent = `Sent to ${people(wentCount(email))}.`;
  const failed = `${email.failed_count} failed`;
  const skipped = `${email.skipped_count} ${email.skipped_count === 1 ? 'was' : 'were'} skipped`;
  const isEveryone = email.failed_count === 0 && email.skipped_count === 0;
  const counts = isEveryone
    ? `${sent} Everyone was sent a copy.${returned}`
    : `${sent} ${failed} and ${skipped}.${returned}`;
  if (email.status !== 'stopped') return counts;
  const who = email.stopped_by ? ` by ${email.stopped_by}` : '';
  return `Stopped${who}. ${counts}`;
}
