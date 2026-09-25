/**
 * The reminders panel of `/portal/system`: run the scan by
 * hand — optionally as a rehearsal — and read the log of what went out.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { ReminderKind, ReminderRunResult, RunAction } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Money } from '@/portal/components/Money';
import { useRunReminders } from './api';
import { KIND_LABELS as REMINDER_KIND_LABELS, ReminderLog } from './ReminderLog';

/** The sentence shown after a run. */
export function runSummary(result: ReminderRunResult, dryRun: boolean): string {
  const verb = dryRun ? 'Would send' : 'Sent';
  const emails = result.sent === 1 ? '1 email' : `${result.sent} emails`;
  return `${verb} ${emails}, skipped ${result.skipped}.`;
}

/** Whether `kind` is one of the reminder kinds `REMINDER_KIND_LABELS` names. */
function isReminderKind(kind: string): kind is ReminderKind {
  return kind in REMINDER_KIND_LABELS;
}

const ACTION_COLUMNS: Column<RunAction>[] = [
  {
    key: 'kind',
    header: 'What',
    render: (row) => (isReminderKind(row.kind) ? REMINDER_KIND_LABELS[row.kind] : row.kind),
  },
  {
    key: 'member',
    header: 'Who',
    render: (row) => (
      <>
        {row.member}
        <span className="muted"> · {row.email}</span>
      </>
    ),
  },
  { key: 'on', header: 'When', render: (row) => <DateText value={row.on} /> },
  {
    key: 'amount_cents',
    header: 'Amount',
    numeric: true,
    render: (row) => <Money cents={row.amount_cents} />,
  },
];

/** The heading over the actions table: what a rehearsal would do, or what a real run did. */
function actionsHeading(dryRun: boolean): string {
  return dryRun ? 'What a live run would do' : 'What this run did';
}

/** Runs the renewal reminder scan on demand and shows its log. */
export function RemindersPanel(): JSX.Element {
  const [dryRun, setDryRun] = useState(true);
  const [lastRunWasDry, setLastRunWasDry] = useState(true);

  const run = useRunReminders();

  const handleRun = (): void => {
    setLastRunWasDry(dryRun);
    run.mutate(dryRun);
  };

  const handleDryRunChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setDryRun(event.target.checked);
  };

  return (
    <Card
      eyebrow="Membership"
      title="Renewal reminders"
      footer={
        <>
          <Button onClick={handleRun} disabled={run.isPending}>
            {run.isPending ? 'Running…' : 'Run now'}
          </Button>
          <label className="cluster">
            <input type="checkbox" checked={dryRun} onChange={handleDryRunChange} />
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

      {run.isSuccess ? (
        <>
          <p role="status">{runSummary(run.data, lastRunWasDry)}</p>
          <h3>{actionsHeading(lastRunWasDry)}</h3>
          <DataTable
            columns={ACTION_COLUMNS}
            rows={run.data.actions}
            rowKey={(row) => `${row.kind}-${row.email}-${row.on ?? ''}-${row.detail}`}
            emptyTitle="Nothing was due"
          />
        </>
      ) : null}

      {run.isError ? (
        <p className="field__error" role="alert">
          {run.error instanceof Error ? run.error.message : 'The reminder run failed.'}
        </p>
      ) : null}

      <ReminderLog />
    </Card>
  );
}
