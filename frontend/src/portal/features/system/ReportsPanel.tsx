/**
 * The scheduled-reports panel of `/portal/system/scheduled`: run the report sender by
 * hand, optionally as a practice run, and read who it reached.
 *
 * The sender mails every emailed report that is due and every DART roster due this
 * month; `/admin/reports` is where the emailed reports and the rosters' recipients are
 * kept.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import { PracticeRunCheckbox } from '@/portal/components/PracticeRunCheckbox';
import { ReportRunOutcome } from '@/portal/features/admin-reports/ReportRunOutcome';
import { useRunScheduledReports } from './api';
import { JobPanel, NothingDue, RunNowButton } from './JobPanel';

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
    <JobPanel
      eyebrow="Reports"
      title="Scheduled reports"
      description="The scheduled reports go every morning at 6:00 AM: every emailed report that is due and, once a month, each DART&rsquo;s roster to the people checked to receive it."
      options={
        <PracticeRunCheckbox
          checked={dryRun}
          onChange={handleDryRunChange}
          task="scheduled reports"
        />
      }
      action={
        <RunNowButton task="scheduled reports" isRunning={run.isPending} onClick={handleRun} />
      }
      isRunning={run.isPending}
      result={<ReportsResult run={run} dryRun={lastRunWasDry} />}
    />
  );
}

interface ReportsResultProps {
  run: ReturnType<typeof useRunScheduledReports>;
  dryRun: boolean;
}

/** What the last report run did, or why it failed; nothing before the first run. */
function ReportsResult({ run, dryRun }: ReportsResultProps): JSX.Element | null {
  if (run.isError) {
    return (
      <p className="field__error" role="alert">
        {run.error instanceof Error ? run.error.message : 'The report run failed.'}
      </p>
    );
  }
  if (!run.isSuccess) return null;
  const { data } = run;
  if (data.actions.length === 0 && data.sent + data.skipped + data.failed === 0) {
    return <NothingDue dryRun={dryRun} />;
  }
  return <ReportRunOutcome result={data} dryRun={dryRun} />;
}
