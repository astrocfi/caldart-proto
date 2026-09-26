/**
 * The year-end statements panel of `/portal/system`: run the statement sender
 * by hand for a chosen year, optionally as a rehearsal, and read who it
 * reached.
 *
 * The sender mails every active account -- a member, a friend, or a donor --
 * with a settled contribution in the chosen year; `/admin/payments/donors` is
 * where a treasurer reads the donors themselves.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { StatementsRunResult } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { RunActionsTable } from '@/portal/components/RunActionsTable';
import { useRunStatements } from './api';

/** The year the panel offers by default: the one the timer sends on January 15th. */
export function defaultStatementYear(today: Date = new Date()): number {
  return today.getFullYear() - 1;
}

/** The sentence shown after a run, in the past tense or the conditional. */
export function statementsRunSummary(result: StatementsRunResult, dryRun: boolean): string {
  const { sent, skipped, failed } = result;
  if (dryRun) return `Would send ${sent}, skip ${skipped}, and fail ${failed}.`;
  return `Sent ${sent}, skipped ${skipped}, and failed ${failed}.`;
}

/** Every statement action reads the same way: one email, the account it reached. */
function statementKindLabel(): string {
  return 'Statement';
}

/** Runs the year-end statement sender on demand and reports what it did. */
export function StatementsPanel(): JSX.Element {
  const [year, setYear] = useState(() => String(defaultStatementYear()));
  const [dryRun, setDryRun] = useState(true);
  const [lastRunWasDry, setLastRunWasDry] = useState(true);

  const run = useRunStatements();

  const handleRun = (): void => {
    setLastRunWasDry(dryRun);
    run.mutate({ year: Number(year), dryRun });
  };

  const handleYearChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setYear(event.target.value);
  };

  const handleDryRunChange = (event: ChangeEvent<HTMLInputElement>): void => {
    setDryRun(event.target.checked);
  };

  return (
    <Card
      eyebrow="Payments"
      title="Year-end statements"
      footer={
        <>
          <Button onClick={handleRun} disabled={run.isPending || year.trim() === ''}>
            {run.isPending ? 'Running…' : 'Run now'}
          </Button>
          <label className="cluster">
            Year
            <input
              type="number"
              inputMode="numeric"
              className="mono"
              style={{ width: '5.5rem' }}
              value={year}
              onChange={handleYearChange}
            />
          </label>
          <label className="cluster">
            <input type="checkbox" checked={dryRun} onChange={handleDryRunChange} />
            Dry run (send nothing)
          </label>
        </>
      }
    >
      <p className="muted">
        The sender also runs once a year, at 06:45 on January 15th, from the{' '}
        <code className="mono">caldart-statements</code> timer, for the year before. It emails every
        active account — a member, a friend, or a donor — that gave a settled contribution in the
        chosen year, with that year&rsquo;s statement PDF attached. Running it again is harmless: an
        account already sent a year&rsquo;s statement is not sent it twice.
      </p>

      {run.isSuccess ? (
        <RunActionsTable
          actions={run.data.actions}
          dryRun={lastRunWasDry}
          kindLabel={statementKindLabel}
          summary={<p role="status">{statementsRunSummary(run.data, lastRunWasDry)}</p>}
        />
      ) : null}

      {run.isError ? (
        <p className="field__error" role="alert">
          {run.error instanceof Error ? run.error.message : 'The statement run failed.'}
        </p>
      ) : null}
    </Card>
  );
}
