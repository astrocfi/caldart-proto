/**
 * The automatic renewal charges panel of `/portal/system/scheduled`: run the
 * daily scan by hand, optionally as a rehearsal, and read the counts it reports.
 *
 * It sits right after the renewal reminder emails panel because the two scans
 * are a pair — the charges run first each morning, so a membership they renew
 * is never also reminded about.
 *
 * A rehearsal runs on one press.  A real run asks first, through the portal's
 * confirmation, because it charges every member whose renewal is due, and a cleared
 * checkbox is a quiet thing to lean a hundred charges on.
 */
import { useRef, useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { RenewalRunResult } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { RunActionsTable } from '@/portal/components/RunActionsTable';
import { useFocusAfterSave } from '@/portal/components/focus';
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

  const run = useRunRenewals();
  // The button is disabled while it runs; it gets the focus back once the run ends.
  const runRef = useRef<HTMLButtonElement>(null);
  useFocusAfterSave(runRef, run.isPending);

  const handleRehearse = (): void => {
    setLastRunWasDry(true);
    run.mutate(true);
  };

  const handleCharge = (): Promise<unknown> => {
    setLastRunWasDry(false);
    return run.mutateAsync(false);
  };

  const handleDryRunChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setDryRun(event.target.checked);
  };

  return (
    <Card
      eyebrow="Membership"
      title="Automatic renewal charges"
      footer={
        <>
          {dryRun ? (
            <Button
              ref={runRef}
              onClick={handleRehearse}
              disabled={run.isPending}
              aria-label={run.isPending ? undefined : 'Run now: automatic renewal charges'}
            >
              {run.isPending ? 'Running…' : 'Run now'}
            </Button>
          ) : (
            <ConfirmButton
              label="Run now"
              name="Run now: automatic renewal charges"
              variant="primary"
              disabled={run.isPending}
              choices={[{ label: 'Charge what is due', variant: 'danger', onChoose: handleCharge }]}
            >
              <p>
                This charges every renewal that is due, for real, and emails each member. Rehearse
                it first if you are not sure what is waiting.
              </p>
            </ConfirmButton>
          )}
          <label className="cluster">
            <input type="checkbox" checked={dryRun} onChange={handleDryRunChange} />
            Practice run: show what would happen, charge nothing
          </label>
        </>
      }
    >
      <p className="muted">
        Charges the saved card or PayPal account of every member whose automatic renewal is due,
        after emailing a notice two weeks ahead and a warning when the card is about to expire. It
        runs every morning before the reminder emails, so a member it renews is not also reminded.
      </p>

      {run.isSuccess ? (
        <RunActionsTable
          actions={run.data.actions}
          dryRun={lastRunWasDry}
          kindLabel={renewalKindLabel}
          summary={<p role="status">{renewalRunSummary(run.data, lastRunWasDry)}</p>}
        />
      ) : null}

      {run.isError ? (
        <p className="field__error" role="alert">
          {run.error instanceof Error ? run.error.message : 'The renewal run failed.'}
        </p>
      ) : null}
    </Card>
  );
}
