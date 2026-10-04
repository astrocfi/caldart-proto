/**
 * Why the signed-in sender cannot send bulk email, in place of the compose form.
 *
 * A DART leader sends to the DART on their own profile, so a leader whose profile
 * names no DART has nobody to send to. The notice says so and links to My profile,
 * where the DART is set. It shows nothing for a sender who can send. The same boxed
 * notice stands on the Dashboard and on every Bulk Email screen a DART leader opens.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import type { BulkEmailSender } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { useBulkSender } from './api';
import './bulk-email.css';

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

/**
 * The notice for the signed-in person, on a screen that does not ask who they may send
 * to on its own, such as the Dashboard.  Only a DART leader can be without a DART to send
 * to, so nobody else is asked, and the notice shows nothing until the answer comes.
 */
export function OwnSenderNotice(): JSX.Element | null {
  const { roles } = useAuth();
  const sender = useBulkSender(roles.includes('dart_leader'));
  return sender.data === undefined ? null : <SenderNotice sender={sender.data} />;
}
