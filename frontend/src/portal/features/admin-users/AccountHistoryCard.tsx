/**
 * The user record's **History** card: who created the account, gave or took away its
 * roles, and deactivated, reactivated, or blocked it, and when, newest first.
 */
import type { JSX } from 'react';

import { Card } from '@/portal/components/Card';
import { changeLine } from './history';
import { useAdminUserHistory } from './api';
import '@/portal/features/admin-aircraft/history.css';

/** The History card for account `userId`. */
export function AccountHistoryCard({ userId }: { userId: number }): JSX.Element {
  const history = useAdminUserHistory(userId);
  return <Card title="History">{historyBody(history)}</Card>;
}

/**
 * The card's body.  An audit card never presents a history it does not have as an empty
 * one: a request still in flight or one that failed each say so.
 */
function historyBody(history: ReturnType<typeof useAdminUserHistory>): JSX.Element {
  if (history.isPending) {
    return (
      <p className="muted" role="status">
        Loading…
      </p>
    );
  }
  if (history.isError) {
    return <p className="muted">The history didn&apos;t load. Try again in a moment.</p>;
  }
  if (history.data.length === 0) {
    return <p className="muted">No change to this account&apos;s roles or status is recorded.</p>;
  }
  return (
    <ul className="record-history">
      {history.data.map((change) => (
        <li key={change.id}>{changeLine(change)}</li>
      ))}
    </ul>
  );
}
