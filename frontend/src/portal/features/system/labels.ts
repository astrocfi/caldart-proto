/**
 * The vocabulary the system screens render: why the reminder scan passed a
 * candidate over.  What an email was for is the server's to say, as each email
 * log row's `purpose_label`.
 */

/**
 * Why a reminder scan skipped a candidate, in the order the guide lists them.
 *
 * The keys are `ReminderRunResult.skipped_by_reason`'s own: `already_sent`,
 * `inactive_user`, `no_email`, `lifetime`, `auto_renew` and `renewed`.
 */
export const SKIPPED_REASON_LABELS: Record<string, string> = {
  already_sent: 'already sent',
  renewed: 'already renewed',
  auto_renew: 'auto-renew on',
  lifetime: 'lifetime member',
  inactive_user: 'account deactivated',
  no_email: 'no address on file',
};
