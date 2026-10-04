import { describe, expect, it } from 'vitest';

import type { AccountChange } from '@/portal/api/types';
import { formatDateTime } from '@/portal/components/DateText';
import { actorName, changeLine, changeWhat } from './history';

const AT = '2026-10-04T22:12:00Z';

function change(overrides: Partial<AccountChange> = {}): AccountChange {
  return {
    id: 1,
    changed_at: AT,
    changed_by: { id: 7, name: 'Nina Kowalski' },
    kind: 'roles',
    added: [],
    removed: [],
    ...overrides,
  };
}

describe('changeWhat', () => {
  it('names the roles a change gave and took away, in words', () => {
    const roles = change({ added: ['verifier', 'treasurer'], removed: ['dart_leader'] });
    expect(changeWhat(roles)).toBe('gave Verifier and Treasurer; took away DART leader');
  });

  it('lists three roles with a serial comma', () => {
    const roles = change({ added: ['verifier', 'treasurer', 'account_admin'] });
    expect(changeWhat(roles)).toBe('gave Verifier, Treasurer, and Account administrator');
  });

  it.each([
    ['created', 'created the account'],
    ['deactivated', 'deactivated the account'],
    ['reactivated', 'reactivated the account'],
    ['blocked', 'blocked reactivation'],
    ['unblocked', 'allowed reactivation'],
  ] as const)('words a %s entry as "%s"', (kind, words) => {
    expect(changeWhat(change({ kind }))).toBe(words);
  });
});

describe('actorName', () => {
  it('calls a change with no account behind it the system', () => {
    expect(actorName(null)).toBe('The system');
  });
});

describe('changeLine', () => {
  it('reads the time, who, and what, in that order', () => {
    expect(changeLine(change({ kind: 'blocked' }))).toBe(
      `${formatDateTime(AT)} · Nina Kowalski · blocked reactivation`,
    );
  });
});
