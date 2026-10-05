/**
 * The wording of a user record's history: one line per change to the account's roles
 * or status, in the words the record's own controls use.
 */
import type { AccountChange, AccountChangeKind } from '@/portal/api/types';
import { roleLabel } from '@/portal/choices';
import { formatDateTime } from '@/portal/components/DateText';

/** Lists role names the way a sentence does: "Verifier, Treasurer, and DART leader". */
const ROLE_LIST = new Intl.ListFormat('en-US', { style: 'long', type: 'conjunction' });

/** What each kind of change did, for every kind but a role change, which names its roles. */
const DID: Record<Exclude<AccountChangeKind, 'roles'>, string> = {
  created: 'created the account',
  deactivated: 'deactivated the account',
  reactivated: 'reactivated the account',
  blocked: 'blocked reactivation',
  unblocked: 'allowed reactivation',
};

/**
 * Who made a change: the account's name, `The system` for a change a management command
 * made, or `A deleted account` for one whose account has since been deleted.
 */
export function actorName(change: Pick<AccountChange, 'changed_by' | 'by_command'>): string {
  if (change.changed_by !== null) return change.changed_by.name;
  return change.by_command ? 'The system' : 'A deleted account';
}

/** What one change did: `gave Verifier and Treasurer; took away DART leader`. */
export function changeWhat(change: AccountChange): string {
  if (change.kind !== 'roles') return DID[change.kind];
  const parts: string[] = [];
  if (change.added.length > 0) parts.push(`gave ${ROLE_LIST.format(change.added.map(roleLabel))}`);
  if (change.removed.length > 0) {
    parts.push(`took away ${ROLE_LIST.format(change.removed.map(roleLabel))}`);
  }
  return parts.length === 0 ? 'changed the roles' : parts.join('; ');
}

/** One history entry as a line: `10/04/2026 at 3:12 PM · Nina Kowalski · gave Verifier`. */
export function changeLine(change: AccountChange): string {
  return `${formatDateTime(change.changed_at)} · ${actorName(change)} · ${changeWhat(change)}`;
}
