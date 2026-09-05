/**
 * The reminders panel of `/portal/system` (PLAN §6.9, §12): run the scan by
 * hand — optionally as a rehearsal — and read the log of what went out.
 */
import { useState } from 'react';

import type { ReminderKind, ReminderLogEntry, ReminderRunResult } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { DataTable } from '../../components/DataTable';
import type { Column } from '../../components/DataTable';
import { DateText } from '../../components/DateText';
import { useReminderLog, useRunReminders } from './api';

/** Kind slug -> what the email actually says (PLAN §4.5). */
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

/** The sentence shown after a run. */
export function runSummary(result: ReminderRunResult, dryRun: boolean): string {
  const verb = dryRun ? 'Would send' : 'Sent';
  const emails = result.sent === 1 ? '1 email' : `${result.sent} emails`;
  return `${verb} ${emails}, skipped ${result.skipped}.`;
}

export function RemindersPanel() {
  const [kind, setKind] = useState<ReminderKind | 'all'>('all');
  const [dryRun, setDryRun] = useState(true);
  const [lastRunWasDry, setLastRunWasDry] = useState(true);

  const log = useReminderLog(kind);
  const run = useRunReminders();

  return (
    <Card
      eyebrow="Membership"
      title="Renewal reminders"
      footer={
        <>
          <Button
            onClick={() => {
              setLastRunWasDry(dryRun);
              run.mutate(dryRun);
            }}
            disabled={run.isPending}
          >
            {run.isPending ? 'Running…' : 'Run now'}
          </Button>
          <label className="cluster">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(event) => setDryRun(event.target.checked)}
            />
            Dry run (send nothing)
          </label>
        </>
      }
    >
      <p className="muted">
        The scan also runs every morning at 07:00 from the{' '}
        <code className="mono">caldart-reminders</code> timer. Running it again is harmless: each
        member gets one email per membership per kind.
      </p>

      {run.isSuccess ? <p role="status">{runSummary(run.data, lastRunWasDry)}</p> : null}

      {run.isError ? (
        <p className="field__error" role="alert">
          {run.error instanceof Error ? run.error.message : 'The reminder run failed.'}
        </p>
      ) : null}

      <DataTable
        columns={COLUMNS}
        rows={log.data?.results ?? []}
        rowKey={(row) => row.id}
        isLoading={log.isPending}
        caption={
          log.data ? `${log.data.count} reminder${log.data.count === 1 ? '' : 's'} sent` : undefined
        }
        emptyTitle="No reminders sent yet"
        emptyDescription="Nothing has matched the 60/30/7-day, expiry or lapsed windows."
        filters={
          <label className="field">
            <span className="field__label">Reminder</span>
            <select
              value={kind}
              onChange={(event) => setKind(event.target.value as ReminderKind | 'all')}
            >
              {KIND_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option === 'all' ? 'All kinds' : KIND_LABELS[option]}
                </option>
              ))}
            </select>
          </label>
        }
      />
    </Card>
  );
}
