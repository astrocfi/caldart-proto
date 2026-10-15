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
 * charges on.  The server takes a real run in its own process, so a slow provider never
 * cuts it off mid-charge, and the panel follows it until it ends.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { RenewalRunResult } from '@/portal/api/types';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import { formatTime } from '@/portal/components/DateText';
import { PracticeRunCheckbox } from '@/portal/components/PracticeRunCheckbox';
import { RunActionsTable } from '@/portal/components/RunActionsTable';
import { useRehearseRenewals, useRenewalScan, useStartRenewals } from './api';
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

  const rehearse = useRehearseRenewals();
  const start = useStartRenewals();
  // The scan the last press started; the hook caches its first answer, so the panel
  // reads as running from the moment the press is answered.
  const scan = useRenewalScan(start.data?.id ?? null);
  const isScanning = start.data !== undefined && scan.data?.finished_at === null;
  const isRunning = rehearse.isPending || start.isPending || isScanning;

  const handleRehearse = (): void => {
    setLastRunWasDry(true);
    rehearse.mutate();
  };

  const handleCharge = (): Promise<unknown> => {
    setLastRunWasDry(false);
    return start.mutateAsync();
  };

  const handleDryRunChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setDryRun(event.target.checked);
  };

  return (
    <JobPanel
      job="renewals"
      eyebrow="Membership"
      title="Automatic renewal charges"
      description="The automatic renewal charges run every morning at 6:30 AM, before the reminder emails, so a member they renew is not also reminded. They charge the saved card or PayPal account of every member whose automatic renewal is due, after emailing a notice two weeks ahead and a warning when the card is about to expire."
      options={
        <PracticeRunCheckbox
          checked={dryRun}
          onChange={handleDryRunChange}
          task="automatic renewal charges"
          leaves="charging anything"
        />
      }
      action={
        dryRun ? (
          <RunNowButton
            task="automatic renewal charges"
            isRunning={isRunning}
            onClick={handleRehearse}
          />
        ) : (
          <ConfirmButton
            label="Run now"
            name="Run now: automatic renewal charges"
            variant="primary"
            disabled={isRunning}
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
      isRunning={isRunning}
      result={
        lastRunWasDry ? (
          <RehearsalResult rehearse={rehearse} />
        ) : (
          <ScanResult start={start} scan={scan} />
        )
      }
    />
  );
}

/** Why a request about the renewal run failed, in the server's words where it gave some. */
function RunFailed({ error }: { error: unknown }): JSX.Element {
  return (
    <p className="field__error" role="alert">
      {error instanceof Error ? error.message : 'The renewal run failed.'}
    </p>
  );
}

interface RehearsalResultProps {
  rehearse: ReturnType<typeof useRehearseRenewals>;
}

/** What the last rehearsal would do, or why it failed; nothing before the first one. */
function RehearsalResult({ rehearse }: RehearsalResultProps): JSX.Element | null {
  if (rehearse.isError) return <RunFailed error={rehearse.error} />;
  if (!rehearse.isSuccess) return null;
  return <RunCounts result={rehearse.data} dryRun />;
}

interface ScanResultProps {
  start: ReturnType<typeof useStartRenewals>;
  scan: ReturnType<typeof useRenewalScan>;
}

/**
 * Where the last live scan has got to. The server runs it in its own process, so
 * the panel reads *Running since 6:31 AM* until the scan finishes, then what it did,
 * or why it stopped.
 */
function ScanResult({ start, scan }: ScanResultProps): JSX.Element | null {
  if (start.isError) return <RunFailed error={start.error} />;
  if (scan.isError) return <RunFailed error={scan.error} />;
  const { data } = scan;
  if (data === undefined) return null;
  if (data.finished_at === null) {
    return <p role="status">Running since {formatTime(data.started_at)}</p>;
  }
  if (!data.ok || data.result === null) {
    return (
      <p className="field__error" role="alert">
        The renewal run stopped: {data.error}
      </p>
    );
  }
  return <RunCounts result={data.result} dryRun={false} />;
}

interface RunCountsProps {
  result: RenewalRunResult;
  dryRun: boolean;
}

/** A finished run's actions table and summary, or that nothing was due. */
function RunCounts({ result, dryRun }: RunCountsProps): JSX.Element {
  const counted = result.noticed + result.warned + result.charged + result.failed + result.paused;
  if (result.actions.length === 0 && counted + result.skipped === 0) {
    return <NothingDue dryRun={dryRun} />;
  }
  return (
    <RunActionsTable
      actions={result.actions}
      dryRun={dryRun}
      kindLabel={renewalKindLabel}
      summary={<p role="status">{renewalRunSummary(result, dryRun)}</p>}
    />
  );
}
