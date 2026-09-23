/**
 * The renewal-reminder log: what went out, to whom and when, filtered by kind.
 *
 * Read-only, and the same table on both screens that show it — the account
 * administrator's Reminders screen and the reminders panel of
 * `/portal/system`.  Running the scan is a system administrator's control and
 * lives in the panel, not here.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { ReminderKind, ReminderLogEntry } from '@/portal/api/types';
import { DataTable } from '@/portal/components/DataTable';
import type { Column } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { useReminderLog } from './api';

/** Kind slug -> what the email actually says. */
export const KIND_LABELS: Record<ReminderKind, string> = {
  t60: '60 days before',
  t30: '30 days before',
  t7: '7 days before',
  expired: 'Expiry day',
  post30: '30 days after',
};

const KIND_OPTIONS: (ReminderKind | 'all')[] = ['all', 't60', 't30', 't7', 'expired', 'post30'];

const COLUMNS: Column<ReminderLogEntry>[] = [
  {
    key: 'sent_at',
    header: 'Sent',
    render: (row) => <DateText value={row.sent_at} withTime />,
    sortValue: (row) => row.sent_at,
  },
  {
    key: 'kind',
    header: 'Reminder',
    render: (row) => KIND_LABELS[row.kind] ?? row.kind,
    sortValue: (row) => row.kind,
  },
  {
    key: 'user_name',
    header: 'Member',
    render: (row) => row.user_name,
    sortValue: (row) => row.user_name,
  },
  {
    key: 'to_email',
    header: 'To',
    render: (row) => <span className="mono">{row.to_email}</span>,
    sortValue: (row) => row.to_email,
  },
];

/** The most recent reminder emails, newest first, with a filter by kind. */
export function ReminderLog(): JSX.Element {
  const [kind, setKind] = useState<ReminderKind | 'all'>('all');
  const log = useReminderLog(kind);

  const handleKindChange = (event: ChangeEvent<HTMLSelectElement>): void => {
    setKind(event.target.value as ReminderKind | 'all');
  };

  return (
    <DataTable
      columns={COLUMNS}
      rows={log.data?.results ?? []}
      rowKey={(row) => row.id}
      isLoading={log.isPending}
      caption={
        log.data ? `${log.data.count} reminder${log.data.count === 1 ? '' : 's'} sent` : undefined
      }
      emptyTitle="No reminders sent yet"
      emptyDescription="Nothing has matched the 60/30/7-day, expiry, or lapsed windows."
      filters={
        <label className="field">
          <span className="field__label">Reminder</span>
          <select value={kind} onChange={handleKindChange}>
            {KIND_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option === 'all' ? 'All kinds' : KIND_LABELS[option]}
              </option>
            ))}
          </select>
        </label>
      }
    />
  );
}
