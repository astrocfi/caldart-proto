/**
 * What one run of the report sender did, or would do: the counts in a
 * sentence, the reasons anything was skipped, the refusals, and the table of
 * every email behind them.  The DART rosters card of `/admin/reports` and the
 * scheduled-reports panel of `/portal/system` both show a run this way.
 */
import type { JSX } from 'react';

import type { ReportRunResult } from '@/portal/api/types';
import { RunActionsTable } from '@/portal/components/RunActionsTable';
import { runSummary } from '@/portal/components/runSummary';
import { reportKindLabel, reportSkippedBreakdown } from './labels';

interface ReportRunOutcomeProps {
  result: ReportRunResult;
  /** Whether the run was a rehearsal, which reads in the conditional. */
  dryRun: boolean;
}

/** A run's summary, skip breakdown, failures and actions, each email named with its report. */
export function ReportRunOutcome({ result, dryRun }: ReportRunOutcomeProps): JSX.Element {
  const breakdown = reportSkippedBreakdown(result.skipped_by_reason);
  return (
    <RunActionsTable
      actions={result.actions}
      dryRun={dryRun}
      kindLabel={reportKindLabel}
      detailHeader="Report or DART"
      summary={
        <>
          <p role="status">{runSummary(result, dryRun)}</p>
          {breakdown === '' ? null : <p className="muted">{breakdown}</p>}
          {result.failed > 0 ? <p className="muted">{`Failed ${result.failed}.`}</p> : null}
        </>
      }
    />
  );
}
