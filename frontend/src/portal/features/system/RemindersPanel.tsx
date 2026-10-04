/**
 * The renewal reminder emails panel of `/portal/system/scheduled`: run the scan by
 * hand, optionally as a practice run, and read the log of what went out under its own
 * heading below.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { ReminderKind } from '@/portal/api/types';
import { PracticeRunCheckbox } from '@/portal/components/PracticeRunCheckbox';
import { RunActionsTable } from '@/portal/components/RunActionsTable';
import { runSummary, skippedBreakdown } from '@/portal/components/runSummary';
import { useReminderSchedule, useRunReminders } from './api';
import { JobPanel, NothingDue, RunNowButton } from './JobPanel';
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

  const handleRun = (): void => {
    setLastRunWasDry(dryRun);
    run.mutate(dryRun);
  };

  const handleDryRunChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setDryRun(event.target.checked);
  };

  return (
    <JobPanel
      eyebrow="Membership"
      title="Renewal reminder emails"
      description={
        <>
          The renewal reminder emails go every morning at 7:00 AM to members whose membership is
          about to expire or has just expired
          {schedule.data ? `: ${schedulePhrase(schedule.data)}` : ''}. They are email only and never
          charge anyone, and a member whose automatic renewal is on is skipped.
        </>
      }
      options={
        <PracticeRunCheckbox
          checked={dryRun}
          onChange={handleDryRunChange}
          task="renewal reminder emails"
        />
      }
      action={
        <RunNowButton
          task="renewal reminder emails"
          isRunning={run.isPending}
          onClick={handleRun}
        />
      }
      isRunning={run.isPending}
      result={<RemindersResult run={run} dryRun={lastRunWasDry} labelKind={reminderKindLabel} />}
    >
      <h3 className="job-panel__subhead">Reminders sent</h3>
      <ReminderLog />
    </JobPanel>
  );
}

interface RemindersResultProps {
  run: ReturnType<typeof useRunReminders>;
  dryRun: boolean;
  labelKind: (kind: string) => string;
}

/** What the last reminder run did, or why it failed; nothing before the first run. */
function RemindersResult({ run, dryRun, labelKind }: RemindersResultProps): JSX.Element | null {
  if (run.isError) {
    return (
      <p className="field__error" role="alert">
        {run.error instanceof Error ? run.error.message : 'The reminder run failed.'}
      </p>
    );
  }
  if (!run.isSuccess) return null;
  const { data } = run;
  if (data.actions.length === 0 && data.sent + data.skipped + data.failed === 0) {
    return <NothingDue dryRun={dryRun} />;
  }
  const breakdown = skippedBreakdown(data.skipped_by_reason, SKIPPED_REASON_LABELS);
  return (
    <RunActionsTable
      actions={data.actions}
      dryRun={dryRun}
      kindLabel={labelKind}
      summary={
        <>
          <p role="status">{runSummary(data, dryRun)}</p>
          {breakdown ? <p className="muted">{breakdown}</p> : null}
          {data.failed > 0 ? <p className="muted">{`Failed ${data.failed}.`}</p> : null}
        </>
      }
    />
  );
}
