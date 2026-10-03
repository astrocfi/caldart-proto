/**
 * Why the signed-in sender cannot send bulk email, in place of the compose form.
 *
 * A DART leader sends to the DART on their own profile, so a leader whose profile
 * names no DART has nobody to send to. The notice says so and links to My profile,
 * where the DART is set. It shows nothing for a sender who can send.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { BulkEmailSender } from '@/portal/api/types';

interface SenderNoticeProps {
  /** Who the signed-in sender may send to, from `GET /bulk-email/sender`. */
  sender: BulkEmailSender;
}

/** The reason a sender cannot send, with the way to fix it; nothing when they can. */
export function SenderNotice({ sender }: SenderNoticeProps): JSX.Element | null {
  if (sender.can_send) return null;
  return (
    <p className="bulk-email__notice" role="status">
      {sender.reason} <Link to="/profile">Open My profile</Link>
    </p>
  );
}
