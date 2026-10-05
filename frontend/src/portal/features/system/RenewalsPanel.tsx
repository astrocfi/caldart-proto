/**
 * The automatic renewal charges panel of `/portal/system/scheduled`: run the
 * daily scan by hand, optionally as a rehearsal, and read the counts it reports.
 *
 * It sits right after the renewal reminder emails panel because the two scans
 * are a pair — the charges run first each morning, so a membership they renew
 * is never also reminded about.
 *
 * A rehearsal runs on one press.  A real run asks first, through the portal's
 * confirmation, which opens on Cancel and closes on Escape, because it charges every
 * member whose renewal is due, and a cleared checkbox is a quiet thing to lean a hundred
 * charges on.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { RenewalRunResult } from '@/portal/api/types';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { PracticeRunCheckbox } from '@/portal/components/PracticeRunCheckbox';
import { RunActionsTable } from '@/portal/components/RunActionsTable';
import { useRunRenewals } from './api';
import { JobPanel, NothingDue, RunNowButton } from './JobPanel';

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
    <JobPanel
      eyebrow="Membership"
      title="Automatic renewal charges"
      description="The automatic renewal charges run every morning at 6:30 AM, before the reminder emails, so a member they renew is not also reminded. They charge the saved card or PayPal account of every member whose automatic renewal is due, after emailing a notice two weeks ahead and a warning when the card is about to expire."
      options={
        <PracticeRunCheckbox
          checked={dryRun}
          onChange={handleDryRunChange}
          task="automatic renewal charges"
          leaves="charge nothing"
        />
      }
      action={
        dryRun ? (
          <RunNowButton
            task="automatic renewal charges"
            isRunning={run.isPending}
            onClick={handleRehearse}
          />
        ) : (
          <ConfirmButton
            label="Run now"
            name="Run now: automatic renewal charges"
            variant="primary"
            disabled={run.isPending}
            keepFocusAfterChoice
            choices={[{ label: 'Charge what is due', variant: 'danger', onChoose: handleCharge }]}
          >
            <p>
              This charges every renewal that is due, for real, and emails each member. Run a
              practice run first if you are not sure what is waiting.
            </p>
          </ConfirmButton>
        )
      }
      isRunning={run.isPending}
      result={<RenewalsResult run={run} dryRun={lastRunWasDry} />}
    />
  );
}

interface RenewalsResultProps {
  run: ReturnType<typeof useRunRenewals>;
  dryRun: boolean;
}

/** What the last renewal run did, or why it failed; nothing before the first run. */
function RenewalsResult({ run, dryRun }: RenewalsResultProps): JSX.Element | null {
  if (run.isError) {
    return (
      <p className="field__error" role="alert">
        {run.error instanceof Error ? run.error.message : 'The renewal run failed.'}
      </p>
    );
  }
  if (!run.isSuccess) return null;
  const { data } = run;
  const counted = data.noticed + data.warned + data.charged + data.failed + data.paused;
  if (data.actions.length === 0 && counted + data.skipped === 0) {
    return <NothingDue dryRun={dryRun} />;
  }
  return (
    <RunActionsTable
      actions={data.actions}
      dryRun={dryRun}
      kindLabel={renewalKindLabel}
      summary={<p role="status">{renewalRunSummary(data, dryRun)}</p>}
    />
  );
}
