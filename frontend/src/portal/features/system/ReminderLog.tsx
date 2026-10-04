/**
 * The renewal-reminder log: what went out, to whom and when, filtered by kind through the
 * shared `FilterBar`, whose blank choice reads "Any kind".  Each kind reads as the stored
 * reminder schedule dates it, such as "60 days before".
 *
 * Read-only, and the same table on both screens that show it — the account
 * administrator's Reminders screen and the renewal reminder emails panel of
 * `/portal/system/scheduled`.  Running the scan is a system administrator's control and
 * lives in the panel, not here.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { ReminderKind, ReminderLogEntry } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { DataTable } from '@/portal/components/DataTable';
import type { Column } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { FilterBar } from '@/portal/components/FilterBar';
import type { FilterField, FilterValues } from '@/portal/reports/types';
import { useReminderLog, useReminderSchedule } from './api';
import { kindLabels, REMINDER_KINDS, schedulePhrase } from './reminderSchedule';

/** The columns after the kind: who the reminder went to.  The address drops first. */
const PERSON_COLUMNS: Column<ReminderLogEntry>[] = [
  {
    key: 'user_name',
    header: 'Member',
    minWidth: '10rem',
    isIdentity: true,
    render: (row) => row.user_name,
    sortValue: (row) => row.user_name,
  },
  {
    key: 'to_email',
    header: 'To',
    minWidth: '14rem',
    dropOrder: 1,
    render: (row) => row.to_email,
    sortValue: (row) => row.to_email,
  },
];

/** The filter's one field, its choices the kinds as the schedule names them. */
function kindField(labels: Record<ReminderKind, string>): FilterField {
  return {
    key: 'kind',
    label: 'Reminder',
    kind: 'select',
    placeholder: 'Any reminder',
    options: REMINDER_KINDS.map((option) => ({ value: option, label: labels[option] })),
  };
}

/** The log's columns, the kind read through `labels`. */
function logColumns(labels: Record<ReminderKind, string>): Column<ReminderLogEntry>[] {
  return [
    {
      key: 'sent_at',
      header: 'Sent',
      width: '12rem',
      noWrap: true,
      render: (row) => <DateText value={row.sent_at} withTime />,
      sortValue: (row) => row.sent_at,
    },
    {
      key: 'kind',
      header: 'Reminder',
      minWidth: '9rem',
      dropOrder: 2,
      render: (row) => labels[row.kind] ?? row.kind,
      sortValue: (row) => row.kind,
    },
    ...PERSON_COLUMNS,
  ];
}

/** The most recent reminder emails, newest first, with a filter by kind. */
export function ReminderLog(): JSX.Element {
  const [values, setValues] = useState<FilterValues>({ kind: '' });
  const kind = (values.kind ?? '') === '' ? 'all' : (values.kind as ReminderKind);
  const log = useReminderLog(kind);
  const schedule = useReminderSchedule();
  const labels = kindLabels(schedule.data);
  const field = kindField(labels);

  const handleFilterChange = (next: FilterValues): void => {
    setValues(next);
  };

  const isFiltered = kind !== 'all';

  return (
    <DataTable
      singleLine
      columns={logColumns(labels)}
      rows={log.data?.results ?? []}
      rowKey={(row) => row.id}
      isLoading={log.isPending}
      caption={
        log.data ? `${log.data.count} reminder${log.data.count === 1 ? '' : 's'} sent` : undefined
      }
      initialSort={{ key: 'sent_at', direction: 'desc' }}
      emptyTitle={isFiltered ? 'No reminders of this kind' : 'No reminders sent yet'}
      emptyDescription={
        isFiltered
          ? undefined
          : schedule.data
            ? `No member has reached a reminder yet. They go ${schedulePhrase(schedule.data)} expiry.`
            : 'No member has reached a reminder yet.'
      }
      emptyAction={
        isFiltered ? (
          <Button variant="secondary" onClick={() => setValues({ kind: '' })}>
            Reset filters
          </Button>
        ) : undefined
      }
      filters={
        <FilterBar
          fields={[field]}
          values={values}
          onChange={handleFilterChange}
          label="Filter the reminders"
        />
      }
    />
  );
}
