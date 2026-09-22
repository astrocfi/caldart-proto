/**
 * The reminders panel of `/portal/system`: run the scan by
 * hand — optionally as a rehearsal — and read the log of what went out.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { ReminderRunResult } from '../../api/types';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { useRunReminders } from './api';
import { ReminderLog } from './ReminderLog';

/** The sentence shown after a run. */
export function runSummary(result: ReminderRunResult, dryRun: boolean): string {
  const verb = dryRun ? 'Would send' : 'Sent';
  const emails = result.sent === 1 ? '1 email' : `${result.sent} emails`;
  return `${verb} ${emails}, skipped ${result.skipped}.`;
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

      {run.isSuccess ? <p role="status">{runSummary(run.data, lastRunWasDry)}</p> : null}

      {run.isError ? (
        <p className="field__error" role="alert">
          {run.error instanceof Error ? run.error.message : 'The reminder run failed.'}
        </p>
      ) : null}

      <ReminderLog />
    </Card>
  );
}
