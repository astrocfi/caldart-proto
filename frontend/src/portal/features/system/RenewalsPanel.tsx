/**
 * The automatic-renewal panel of `/portal/system`: run the daily scan by hand,
 * optionally as a rehearsal, and read the counts it reports.
 *
 * It sits beside the reminders panel because the two scans are a pair — the
 * renewals one runs first each morning, so a membership it renews is never
 * also nagged about.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { RenewalRunResult } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { useRunRenewals } from './api';

/** The sentence shown after a run, in the past tense or the conditional. */
export function renewalRunSummary(result: RenewalRunResult, dryRun: boolean): string {
  const { noticed, warned, charged, failed, paused, skipped } = result;
  if (dryRun) {
    return (
      `Would notice ${noticed}, warn ${warned}, charge ${charged}, ` +
      `fail ${failed}, pause ${paused}, and skip ${skipped}.`
    );
  }
  return (
    `Noticed ${noticed}, warned ${warned}, charged ${charged}, ` +
    `failed ${failed}, paused ${paused}, and skipped ${skipped}.`
  );
}

/** Runs the automatic-renewal scan on demand and reports what it did. */
export function RenewalsPanel(): JSX.Element {
  const [dryRun, setDryRun] = useState(true);
  const [lastRunWasDry, setLastRunWasDry] = useState(true);

  const run = useRunRenewals();

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
      title="Automatic renewals"
      footer={
        <>
          <Button onClick={handleRun} disabled={run.isPending}>
            {run.isPending ? 'Running…' : 'Run now'}
          </Button>
          <label className="cluster">
            <input type="checkbox" checked={dryRun} onChange={handleDryRunChange} />
            Dry run (charge nothing)
          </label>
        </>
      }
    >
      <p className="muted">
        The scan also runs every morning at 06:30 from the{' '}
        <code className="mono">caldart-renewals</code> timer, half an hour before the reminders. It
        sends the fortnight&rsquo;s warning, warns about a card that is about to expire, and charges
        whatever is due. Running it again is harmless: every scheduled charge records what has
        already gone out.
      </p>

      {run.isSuccess ? <p role="status">{renewalRunSummary(run.data, lastRunWasDry)}</p> : null}

      {run.isError ? (
        <p className="field__error" role="alert">
          {run.error instanceof Error ? run.error.message : 'The renewal run failed.'}
        </p>
      ) : null}
    </Card>
  );
}
