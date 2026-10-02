/**
 * The renewal-reminder log: what went out, to whom and when, filtered by kind.  Each kind
 * reads as the stored reminder schedule dates it, such as "60 days before".
 *
 * Read-only, and the same table on both screens that show it — the account
 * administrator's Reminders screen and the renewal reminder emails panel of
 * `/portal/system/scheduled`.  Running the scan is a system administrator's control and
 * lives in the panel, not here.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { ReminderKind, ReminderLogEntry } from '@/portal/api/types';
import { DataTable } from '@/portal/components/DataTable';
import type { Column } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { useReminderLog, useReminderSchedule } from './api';
import { kindLabels, REMINDER_KINDS, schedulePhrase } from './reminderSchedule';

/** The columns after the kind: who the reminder went to. */
const PERSON_COLUMNS: Column<ReminderLogEntry>[] = [
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

/** The log's columns, the kind read through `labels`. */
function logColumns(labels: Record<ReminderKind, string>): Column<ReminderLogEntry>[] {
  return [
    {
      key: 'sent_at',
      header: 'Sent',
      render: (row) => <DateText value={row.sent_at} withTime />,
      sortValue: (row) => row.sent_at,
    },
    {
      key: 'kind',
      header: 'Reminder',
      render: (row) => labels[row.kind] ?? row.kind,
      sortValue: (row) => row.kind,
    },
    ...PERSON_COLUMNS,
  ];
}

/** The most recent reminder emails, newest first, with a filter by kind. */
export function ReminderLog(): JSX.Element {
  const [kind, setKind] = useState<ReminderKind | 'all'>('all');
  const log = useReminderLog(kind);
  const schedule = useReminderSchedule();
  const labels = kindLabels(schedule.data);

  const handleKindChange = (event: ChangeEvent<HTMLSelectElement>): void => {
    setKind(event.target.value as ReminderKind | 'all');
  };

  return (
    <DataTable
      columns={logColumns(labels)}
      rows={log.data?.results ?? []}
      rowKey={(row) => row.id}
      isLoading={log.isPending}
      caption={
        log.data ? `${log.data.count} reminder${log.data.count === 1 ? '' : 's'} sent` : undefined
      }
      emptyTitle="No reminders sent yet"
      emptyDescription={
        schedule.data
          ? `No member has reached a reminder yet. They go ${schedulePhrase(schedule.data)} expiry.`
          : 'No member has reached a reminder yet.'
      }
      filters={
        <label className="field">
          <span className="field__label">Reminder</span>
          <select value={kind} onChange={handleKindChange}>
            <option value="all">All kinds</option>
            {REMINDER_KINDS.map((option) => (
              <option key={option} value={option}>
                {labels[option]}
              </option>
            ))}
          </select>
        </label>
      }
    />
  );
}
