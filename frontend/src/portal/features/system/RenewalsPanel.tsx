/**
 * The automatic-renewal panel of `/portal/system`: run the daily scan by hand,
 * optionally as a rehearsal, and read the counts it reports.
 *
 * It sits beside the reminders panel because the two scans are a pair — the
 * renewals one runs first each morning, so a membership it renews is never
 * also nagged about.
 *
 * A rehearsal runs on one press.  A real run asks first, because it charges
 * every member whose renewal is due, and a cleared checkbox is a quiet thing
 * to lean a hundred charges on.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { RenewalRunResult } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { RunActionsTable } from '@/portal/components/RunActionsTable';
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

/**
 * What each email template name, or a charge, reads as in the actions table.
 * `renewal_charged` reads by the charge itself, not "renewed", because a
 * contribution-only mandate's charge renews no membership.
 */
const ACTION_KIND_LABELS: Record<string, string> = {
  renewal_notice: 'Notice',
  renewal_card_expiring: 'Card expiring warning',
  renewal_charged: 'Charge taken notice',
  renewal_failed: 'Charge failed notice',
  charge: 'Charge',
};

/** A renewal run's own kind vocabulary, for the shared actions table. */
function renewalKindLabel(kind: string): string {
  return ACTION_KIND_LABELS[kind] ?? kind;
}

/** Runs the automatic-renewal scan on demand and reports what it did. */
export function RenewalsPanel(): JSX.Element {
  const [dryRun, setDryRun] = useState(true);
  const [lastRunWasDry, setLastRunWasDry] = useState(true);
  const [isConfirming, setIsConfirming] = useState(false);

  const run = useRunRenewals();

  const start = (): void => {
    setLastRunWasDry(dryRun);
    setIsConfirming(false);
    run.mutate(dryRun);
  };

  const handleRun = (): void => {
    if (dryRun) {
      start();
      return;
    }
    setIsConfirming(true);
  };

  const handleConfirm = (): void => {
    start();
  };

  const handleCancelRun = (): void => {
    setIsConfirming(false);
  };

  const handleDryRunChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setDryRun(event.target.checked);
    setIsConfirming(false);
  };

  return (
    <Card
      eyebrow="Membership"
      title="Automatic renewals"
      footer={
        isConfirming ? (
          <>
            <Button variant="danger" onClick={handleConfirm} disabled={run.isPending}>
              Yes, charge what is due
            </Button>
            <Button variant="quiet" onClick={handleCancelRun}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button onClick={handleRun} disabled={run.isPending}>
              {run.isPending ? 'Running…' : 'Run now'}
            </Button>
            <label className="cluster">
              <input type="checkbox" checked={dryRun} onChange={handleDryRunChange} />
              Dry run (charge nothing)
            </label>
          </>
        )
      }
    >
      <p className="muted">
        The scan also runs every morning at 06:30 from the{' '}
        <code className="mono">caldart-renewals</code> timer, half an hour before the reminders. It
        sends the fortnight&rsquo;s warning, warns about a card that is about to expire, and charges
        whatever is due. Running it again is harmless: every scheduled charge records what has
        already gone out.
      </p>

      {isConfirming ? (
        <p role="status">
          This charges every renewal that is due, for real, and emails each member. Rehearse it
          first if you are not sure what is waiting.
        </p>
      ) : null}

      {run.isSuccess && !isConfirming ? (
        <>
          <p role="status">{renewalRunSummary(run.data, lastRunWasDry)}</p>
          <RunActionsTable
            actions={run.data.actions}
            dryRun={lastRunWasDry}
            kindLabel={renewalKindLabel}
          />
        </>
      ) : null}

      {run.isError ? (
        <p className="field__error" role="alert">
          {run.error instanceof Error ? run.error.message : 'The renewal run failed.'}
        </p>
      ) : null}
    </Card>
  );
}
