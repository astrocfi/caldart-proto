/**
 * A bulk email's people as the rows of a `RunActionsTable`.
 *
 * A preview's people read **To send** or **Skipped**, and a sent email's read
 * **Sent**, **Failed**, or **Skipped**, each with its reason in the detail column.
 * Nobody is sent anything about a particular day, so no row carries a date or an
 * amount.
 */
import type {
  BulkEmailDetail,
  BulkEmailPreview,
  BulkEmailPreviewRecipient,
  BulkEmailRecipientStatus,
  RunAction,
} from '@/portal/api/types';

/** The kind of a preview's row for somebody who will be sent a copy. */
const TO_SEND = 'to_send';

/** What each row's kind reads as. */
const RESULT_LABELS: Record<BulkEmailRecipientStatus | typeof TO_SEND, string> = {
  to_send: 'To send',
  pending: 'Not sent',
  sent: 'Sent',
  failed: 'Failed',
  skipped: 'Skipped',
};

/** A row's kind in words, or the kind itself for one this screen does not know. */
export function resultLabel(kind: string): string {
  return kind in RESULT_LABELS ? RESULT_LABELS[kind as keyof typeof RESULT_LABELS] : kind;
}

function action(kind: string, name: string, email: string, reason: string): RunAction {
  return { kind, member: name, email, on: null, amount_cents: null, detail: reason };
}

function previewAction(kind: string, person: BulkEmailPreviewRecipient): RunAction {
  return action(kind, person.name, person.email, person.reason);
}

/** A preview's people: everybody to be sent a copy, then everybody skipped. */
export function previewActions(preview: BulkEmailPreview): RunAction[] {
  return [
    ...preview.recipients.map((person) => previewAction(TO_SEND, person)),
    ...preview.skipped.map((person) => previewAction('skipped', person)),
  ];
}

/** A sent bulk email's people, in the order the send stored them. */
export function resultActions(sent: BulkEmailDetail): RunAction[] {
  return sent.recipients.map((person) =>
    action(person.status, person.name, person.email, person.reason),
  );
}

/**
 * `Sent 12, failed 1, skipped 2.`: what one send came to.  A send that stopped
 * part way says so first, and how many copies were never sent.
 */
export function sentSummary(sent: BulkEmailDetail): string {
  const counts = `Sent ${sent.sent_count}, failed ${sent.failed_count}, skipped ${sent.skipped_count}.`;
  if (sent.sent_at !== null) return counts;
  const unsent = sent.recipients.filter((person) => person.status === 'pending').length;
  return `Interrupted: ${counts} Not sent ${unsent}.`;
}

/** `3 people`: a list's caption. */
export function peopleCaption(count: number): string {
  return count === 1 ? '1 person' : `${count} people`;
}

/** `12 people will be sent this email; 2 are skipped.`: what a preview found. */
export function previewSummary(preview: BulkEmailPreview): string {
  const people = preview.count === 1 ? '1 person' : `${preview.count} people`;
  const skipped =
    preview.skipped_count === 1 ? '1 is skipped' : `${preview.skipped_count} are skipped`;
  return `${people} will be sent this email; ${skipped}.`;
}

/** `Send to 12 people`: the send button's words. */
export function sendLabel(count: number): string {
  return count === 1 ? 'Send to 1 person' : `Send to ${count} people`;
}
