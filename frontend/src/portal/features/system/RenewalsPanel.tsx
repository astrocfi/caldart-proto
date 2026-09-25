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

import type { RenewalRunResult, RunAction } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import type { Column } from '@/portal/components/DataTable';
import { DataTable } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { Money } from '@/portal/components/Money';
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

/** What each email template name, or a charge, reads as in the actions table. */
const ACTION_KIND_LABELS: Record<string, string> = {
  renewal_notice: 'Notice',
  renewal_card_expiring: 'Card expiring warning',
  renewal_charged: 'Renewed notice',
  renewal_failed: 'Charge failed notice',
  charge: 'Charge',
};

const ACTION_COLUMNS: Column<RunAction>[] = [
  { key: 'kind', header: 'What', render: (row) => ACTION_KIND_LABELS[row.kind] ?? row.kind },
  {
    key: 'member',
    header: 'Who',
    render: (row) => (
      <>
        {row.member}
        <span className="muted"> · {row.email}</span>
      </>
    ),
  },
  { key: 'on', header: 'When', render: (row) => <DateText value={row.on} /> },
  {
    key: 'amount_cents',
    header: 'Amount',
    numeric: true,
    render: (row) => <Money cents={row.amount_cents} />,
  },
];

/** The heading over the actions table: what a rehearsal would do, or what a real run did. */
function actionsHeading(dryRun: boolean): string {
  return dryRun ? 'What a live run would do' : 'What this run did';
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
          <h3>{actionsHeading(lastRunWasDry)}</h3>
          <DataTable
            columns={ACTION_COLUMNS}
            rows={run.data.actions}
            rowKey={(row) => `${row.kind}-${row.email}-${row.on ?? ''}-${row.detail}`}
            emptyTitle="Nothing was due"
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
