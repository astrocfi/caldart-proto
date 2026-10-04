/**
 * The bounces panel of `/portal/system/scheduled`: read the bounce mailbox by hand,
 * optionally as a practice run, and see which emails bounced.  When no bounce mailbox
 * is set up the panel says so as it loads and holds **Run now** back.
 *
 * The check runs every hour on its own. A report it can tie to an email marks that
 * email **Bounced** in the email log and flags the address on its account; one it
 * cannot is listed as unmatched. A rehearsal changes nothing and leaves every report
 * unread for the next run.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { BounceRunResult } from '@/portal/api/types';
import { PracticeRunCheckbox } from '@/portal/components/PracticeRunCheckbox';
import { RunActionsTable } from '@/portal/components/RunActionsTable';
import { useBounceStatus, useRunBounces } from './api';
import { JobPanel, NothingDue, RunNowButton } from './JobPanel';

/** What the panel says, as it loads, when no bounce mailbox is set up. */
export const BOUNCES_OFF =
  'Bounce checking is off. Ask the person who installed the site to set up a bounce mailbox.';

/** The sentence shown after a run, in the past tense or the conditional. */
export function bounceRunSummary(result: BounceRunResult, dryRun: boolean): string {
  const { bounced, unmatched, ignored, skipped } = result;
  if (dryRun) {
    return (
      `Would mark ${bounced} bounced, leave ${unmatched} unmatched, ignore ${ignored}, ` +
      `and skip ${skipped}.`
    );
  }
  return (
    `Marked ${bounced} bounced, left ${unmatched} unmatched, ignored ${ignored}, ` +
    `and skipped ${skipped}.`
  );
}

/** What each kind of action reads as in the actions table. */
const KIND_LABELS: Record<string, string> = {
  bounced: 'Bounced',
  unmatched: 'No matching email',
};

/** How a bounce run's own `kind` slug reads in the actions table. */
function bounceKindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

/** Runs the bounce check on demand and reports what it found. */
export function BouncesPanel(): JSX.Element {
  const [dryRun, setDryRun] = useState(true);
  const [lastRunWasDry, setLastRunWasDry] = useState(true);

  const status = useBounceStatus();
  const run = useRunBounces();
  // Off once the server says so, or once a run finds it off.
  const isOff = status.data?.enabled === false || run.data?.enabled === false;

  const handleRun = (): void => {
    setLastRunWasDry(dryRun);
    run.mutate(dryRun);
  };

  const handleDryRunChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setDryRun(event.target.checked);
  };

  return (
    <JobPanel
      eyebrow="Email"
      title="Bounces"
      description="The bounce check runs every hour. It reads the mailbox that undeliverable email comes back to, marks each email another mail server refused for good as Bounced on the Sent emails page, and flags the address on the person&rsquo;s member and user records until it changes, is verified, or a user administrator clears it. Delays and temporary failures are ignored."
      notice={isOff ? <p className="job-panel__notice">{BOUNCES_OFF}</p> : null}
      options={
        <PracticeRunCheckbox
          checked={dryRun}
          onChange={handleDryRunChange}
          task="bounce check"
          leaves="change nothing"
        />
      }
      action={
        <RunNowButton
          task="bounce check"
          isRunning={run.isPending}
          disabled={isOff}
          onClick={handleRun}
        />
      }
      isRunning={run.isPending}
      result={<BouncesResult run={run} dryRun={lastRunWasDry} />}
    />
  );
}

interface BouncesResultProps {
  run: ReturnType<typeof useRunBounces>;
  dryRun: boolean;
}

/** What the last bounce check found, or why it failed; nothing before the first run. */
function BouncesResult({ run, dryRun }: BouncesResultProps): JSX.Element | null {
  if (run.isError) {
    return (
      <p className="field__error" role="alert">
        {run.error instanceof Error ? run.error.message : 'The bounce check failed.'}
      </p>
    );
  }
  // A run that found checking off says so in the notice above Run now.
  if (!run.isSuccess || !run.data.enabled) return null;
  const { data } = run;
  if (
    data.actions.length === 0 &&
    data.bounced + data.unmatched + data.ignored + data.skipped === 0
  ) {
    return <NothingDue dryRun={dryRun} />;
  }
  return (
    <RunActionsTable
      actions={data.actions}
      dryRun={dryRun}
      kindLabel={bounceKindLabel}
      detailHeader="Report"
      summary={<p role="status">{bounceRunSummary(data, dryRun)}</p>}
    />
  );
}
