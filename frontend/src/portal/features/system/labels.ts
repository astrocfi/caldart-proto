/**
 * The vocabularies the system screens render: what an email was for, and why
 * the reminder scan passed a candidate over.
 */

/**
 * An email's purpose, in the order the email log's picker offers it.
 *
 * The keys are the template names `GET /system/emails` reports; the purposes
 * are not a fixed enumeration, so a template the labels below do not name
 * still reads through {@link purposeLabel}, by its raw slug.
 */
export const PURPOSE_LABELS: Record<string, string> = {
  reminder_t60: 'Renewal reminder (60 days)',
  reminder_t30: 'Renewal reminder (30 days)',
  reminder_t7: 'Renewal reminder (7 days)',
  reminder_expired: 'Renewal reminder (expired)',
  reminder_post30: 'Renewal reminder (30 days after)',
  renewal_enabled: 'Renewal turned on',
  renewal_notice: 'Renewal notice',
  renewal_card_expiring: 'Card expiring',
  renewal_charged: 'Renewal charged',
  renewal_failed: 'Renewal declined',
  renewal_canceled: 'Renewal turned off',
  receipt: 'Receipt',
  refund: 'Refund',
  member_invitation: 'Invitation',
  password_reset: 'Password reset',
};

/** `purpose`'s label, or the raw slug when it names no template above. */
export function purposeLabel(purpose: string): string {
  return PURPOSE_LABELS[purpose] ?? purpose;
}

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
