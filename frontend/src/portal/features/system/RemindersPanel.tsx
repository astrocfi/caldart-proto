/**
 * The renewal reminder emails panel of `/portal/system/scheduled`: run the scan
 * by hand — optionally as a rehearsal — and read the log of what went out.
 */
import { useRef, useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { ReminderKind } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { RunActionsTable } from '@/portal/components/RunActionsTable';
import { runSummary, skippedBreakdown } from '@/portal/components/runSummary';
import { useFocusAfterSave } from '@/portal/components/focus';
import { useReminderSchedule, useRunReminders } from './api';
import { SKIPPED_REASON_LABELS } from './labels';
import { ReminderLog } from './ReminderLog';
import { kindLabels, REMINDER_KINDS, schedulePhrase } from './reminderSchedule';

/** Whether `kind` is one of the reminder kinds. */
function isReminderKind(kind: string): kind is ReminderKind {
  return (REMINDER_KINDS as readonly string[]).includes(kind);
}

/** Runs the renewal reminder scan on demand and shows its log. */
export function RemindersPanel(): JSX.Element {
  const [dryRun, setDryRun] = useState(true);
  const [lastRunWasDry, setLastRunWasDry] = useState(true);

  const schedule = useReminderSchedule();
  const labels = kindLabels(schedule.data);
  // A reminder run's own kind vocabulary, for the shared actions table.
  const reminderKindLabel = (kind: string): string => (isReminderKind(kind) ? labels[kind] : kind);

  const run = useRunReminders();
  // The button is disabled while it runs; it gets the focus back once the run ends.
  const runRef = useRef<HTMLButtonElement>(null);
  useFocusAfterSave(runRef, run.isPending);
  const breakdown = run.data
    ? skippedBreakdown(run.data.skipped_by_reason, SKIPPED_REASON_LABELS)
    : '';

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
      title="Renewal reminder emails"
      footer={
        <>
          <Button
            ref={runRef}
            onClick={handleRun}
            disabled={run.isPending}
            aria-label={run.isPending ? undefined : 'Run now: renewal reminder emails'}
          >
            {run.isPending ? 'Running…' : 'Run now'}
          </Button>
          <label className="cluster">
            <input type="checkbox" checked={dryRun} onChange={handleDryRunChange} />
            Practice run: show what would happen, send nothing
          </label>
        </>
      }
    >
      <p className="muted">
        Emails members whose membership is about to expire or has just expired
        {schedule.data ? `: ${schedulePhrase(schedule.data)}` : ''}. It sends email only and never
        charges anyone. A member whose automatic renewal is on is skipped. It runs every morning.
      </p>

      {run.isSuccess ? (
        <RunActionsTable
          actions={run.data.actions}
          dryRun={lastRunWasDry}
          kindLabel={reminderKindLabel}
          summary={
            <>
              <p role="status">{runSummary(run.data, lastRunWasDry)}</p>
              {breakdown ? <p className="muted">{breakdown}</p> : null}
              {run.data.failed > 0 ? <p className="muted">{`Failed ${run.data.failed}.`}</p> : null}
            </>
          }
        />
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
