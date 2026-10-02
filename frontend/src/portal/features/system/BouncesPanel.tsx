/**
 * The bounces panel of `/portal/system/scheduled`: read the bounce mailbox by hand,
 * optionally as a rehearsal, and see which emails bounced.
 *
 * The check runs every hour on its own. A report it can tie to an email marks that
 * email **Bounced** in the email log and flags the address on its account; one it
 * cannot is listed as unmatched. A rehearsal changes nothing and leaves every report
 * unread for the next run.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { BounceRunResult } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { RunActionsTable } from '@/portal/components/RunActionsTable';
import { useRunBounces } from './api';

/** What the panel says when no bounce mailbox is configured. */
export const BOUNCES_OFF =
  'Bounce checking is off: no bounce mailbox is configured. The server operator sets one up.';

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

function bounceKindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? kind;
}

/** Runs the bounce check on demand and reports what it found. */
export function BouncesPanel(): JSX.Element {
  const [dryRun, setDryRun] = useState(true);
  const [lastRunWasDry, setLastRunWasDry] = useState(true);

  const run = useRunBounces();

  const handleRun = (): void => {
    setLastRunWasDry(dryRun);
    run.mutate(dryRun);
  };

  const handleDryRunChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setDryRun(event.target.checked);
  };

  return (
    <Card
      eyebrow="Email"
      title="Bounces"
      footer={
        <>
          <Button onClick={handleRun} disabled={run.isPending}>
            {run.isPending ? 'Running…' : 'Run now'}
          </Button>
          <label className="cluster">
            <input type="checkbox" checked={dryRun} onChange={handleDryRunChange} />
            Dry run (change nothing)
          </label>
        </>
      }
    >
      <p className="muted">
        Every hour the server reads the mailbox that undeliverable email is returned to. Each
        message another mail server refused for good is marked Bounced on the Sent Emails page, and
        the address is flagged on the person&rsquo;s member and user records until it changes, is
        verified, or a user administrator clears it. Delays and temporary failures are ignored.
      </p>

      {run.isSuccess && !run.data.enabled ? <p role="status">{BOUNCES_OFF}</p> : null}

      {run.isSuccess && run.data.enabled ? (
        <RunActionsTable
          actions={run.data.actions}
          dryRun={lastRunWasDry}
          kindLabel={bounceKindLabel}
          detailHeader="Report"
          summary={<p role="status">{bounceRunSummary(run.data, lastRunWasDry)}</p>}
        />
      ) : null}

      {run.isError ? (
        <p className="field__error" role="alert">
          {run.error instanceof Error ? run.error.message : 'The bounce check failed.'}
        </p>
      ) : null}
    </Card>
  );
}
