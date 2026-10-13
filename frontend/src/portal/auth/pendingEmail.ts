/** The wording of a change of sign-in address that waits for its link to be followed. */
import type { User } from '@/portal/api/types';

/**
 * The sentence that says a change of address is waiting, or `null` when none is:
 * `We sent a link to <pending>. Your sign-in address stays <email> until you follow it.`
 *
 * @param user - The signed-in user, whose `pending_email` is `''` with no change waiting.
 */
export function pendingEmailNotice(user: Pick<User, 'email' | 'pending_email'>): string | null {
  if (user.pending_email === '') return null;
  return `We sent a link to ${user.pending_email}. Your sign-in address stays ${user.email} until you follow it.`;
}

/**
 * What an administrator's record says about a change of address that waits, or `null`
 * when none does: `Waiting for <pending> to confirm. The address changes when the link
 * sent there is followed.`
 *
 * @param pendingEmail - The record's `pending_email`, `''` with no change waiting.
 */
export function pendingEmailStatus(pendingEmail: string): string | null {
  if (pendingEmail === '') return null;
  return `Waiting for ${pendingEmail} to confirm. The address changes when the link sent there is followed.`;
}
