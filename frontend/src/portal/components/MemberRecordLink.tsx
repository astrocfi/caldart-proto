/**
 * "Member record": a link to an account's member record, for a reader who can open one.
 *
 * The finance and users screens name people the member list may not hold, such as a
 * donor, who is on no member list at all; this link is how an account administrator
 * reaches that person's record from there.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { useAuth } from '@/portal/auth/useAuth';
import { hasAnyRole } from '@/portal/nav';

interface MemberRecordLinkProps {
  /** The account's user id. */
  userId: number;
  /** True for a "Deleted member N" account, whose record cannot be changed. */
  isTombstone?: boolean;
}

/**
 * A **Member record** link to `/admin/members/{userId}`, shown only to a reader holding
 * `account_admin` (a system administrator passes too), and never for a "Deleted member
 * N" account.
 *
 * @returns The link, or null when the reader cannot use it or the account is a tombstone.
 */
export function MemberRecordLink({
  userId,
  isTombstone = false,
}: MemberRecordLinkProps): JSX.Element | null {
  const { roles } = useAuth();
  if (isTombstone || !hasAnyRole(roles, ['account_admin'])) return null;
  return <Link to={`/admin/members/${userId}`}>Member record</Link>;
}
