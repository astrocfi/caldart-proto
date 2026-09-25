/**
 * The scheduled-reports panel of `/portal/system`: run the report sender by
 * hand, optionally as a rehearsal, and read who it reached.
 *
 * The sender mails every report subscription that is due and every DART roster
 * due this month; `/admin/reports` is where the subscriptions and the rosters'
 * recipients are kept.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { ReportRunOutcome } from '@/portal/features/admin-reports/ReportRunOutcome';
import { useRunScheduledReports } from './api';

/** Runs the report sender on demand and reports what it sent. */
export function ReportsPanel(): JSX.Element {
  const [dryRun, setDryRun] = useState(true);
  const [lastRunWasDry, setLastRunWasDry] = useState(true);

  const run = useRunScheduledReports();

  const handleRun = (): void => {
    setLastRunWasDry(dryRun);
    run.mutate(dryRun);
  };

  const handleDryRunChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setDryRun(event.target.checked);
  };

  return (
    <Card
      eyebrow="Reports"
      title="Scheduled reports"
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
        The sender also runs every morning at 06:00 from the{' '}
        <code className="mono">caldart-reports</code> timer. It emails every report subscription
        that is due and, once a month, each DART&rsquo;s roster to the people ticked to receive it.
        Running it again is harmless: a subscription that has gone out is not due again until its
        next date, and a DART gets one roster a month.
      </p>

      {run.isSuccess ? <ReportRunOutcome result={run.data} dryRun={lastRunWasDry} /> : null}

      {run.isError ? (
        <p className="field__error" role="alert">
          {run.error instanceof Error ? run.error.message : 'The report run failed.'}
        </p>
      ) : null}
    </Card>
  );
}
