/** Where the member record leads back to: the member list, or the donors report for a donor. */
import type { MemberDetail, RoleSlug } from '@/portal/api/types';
import { hasAnyRole } from '@/portal/nav';

/** A screen the record leads back to, and the words on the link that goes there. */
export interface RecordHome {
  to: string;
  label: string;
}

const MEMBER_LIST: RecordHome = { to: '/admin/members', label: 'Back to members' };
const DONORS_REPORT: RecordHome = { to: '/admin/payments/donors', label: 'Back to donors' };

/**
 * The screen the record of `member` leads back to, and where a delete lands, for a
 * reader holding `roles`.
 *
 * A donor is on no member list: the donors report is where a reader found one, and
 * where a deleted donor's gifts show under the tombstone's name, so a donor's record
 * leads there for a reader who opens that report. Every other record, and a donor's
 * for a reader without the report, leads to the member list.
 *
 * @param member - The record on screen; only its kind is read.
 * @param roles - The signed-in reader's roles.
 * @returns The path and the link's label.
 */
export function recordHome(
  member: Pick<MemberDetail, 'kind'>,
  roles: readonly RoleSlug[],
): RecordHome {
  if (member.kind === 'donor' && hasAnyRole(roles, ['treasurer'])) return DONORS_REPORT;
  return MEMBER_LIST;
}
