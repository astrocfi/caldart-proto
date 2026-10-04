/**
 * The vocabulary the system screens render: why the reminder scan passed a
 * candidate over, and what a refused send's error means.  What an email was for is
 * the server's to say, as each email log row's `purpose_label`.
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

/**
 * What a refused send's recorded error means, in words, keyed by the exception's name
 * as the email log records it.
 */
const SEND_ERROR_WORDS: Record<string, string> = {
  SMTPRecipientsRefused: 'The mail server refused the address.',
  SMTPSenderRefused: "The mail server refused the site's sending address.",
  SMTPDataError: 'The mail server refused the message.',
  SMTPAuthenticationError: 'The site could not sign in to the mail server.',
  SMTPConnectError: 'The site could not reach the mail server.',
  ConnectionRefusedError: 'The site could not reach the mail server.',
  gaierror: 'The site could not find the mail server.',
  SMTPServerDisconnected: 'The mail server hung up before the email went.',
  TimeoutError: 'The mail server did not answer in time.',
};

/** What a send error means, such as *The mail server refused the address.*. */
export function sendErrorWords(error: string): string {
  return SEND_ERROR_WORDS[error] ?? 'The mail server would not take it.';
}
