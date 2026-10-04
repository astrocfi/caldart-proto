/**
 * The year-end statements panel of `/portal/system/scheduled`: run the statement sender
 * by hand for a chosen year, optionally as a practice run, and read who it
 * reached.
 *
 * The sender mails every active account -- a member, a friend, or a donor --
 * with a settled contribution in the chosen year; `/admin/payments/donors` is
 * where a treasurer reads the donors themselves.
 */
import { useState } from 'react';
import type { ChangeEvent, JSX } from 'react';

import type { StatementsRunResult } from '@/portal/api/types';
import { Field } from '@/portal/components/Field';
import { PracticeRunCheckbox } from '@/portal/components/PracticeRunCheckbox';
import { RunActionsTable } from '@/portal/components/RunActionsTable';
import { useRunStatements } from './api';
import { JobPanel, NothingDue, RunNowButton } from './JobPanel';

/** The year the panel offers by default: the one the January run sends. */
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
    <JobPanel
      eyebrow="Payments"
      title="Year-end statements"
      description="The year-end statements go once a year, on January 15th at 6:45 AM, for the year before. Every active member, friend, or donor who gave a settled contribution in the chosen year is emailed that year&rsquo;s statement as a PDF."
      options={
        <>
          <Field label="Year">
            {(field) => (
              <input
                {...field}
                type="number"
                inputMode="numeric"
                className="job-panel__year"
                value={year}
                onChange={handleYearChange}
              />
            )}
          </Field>
          <PracticeRunCheckbox
            checked={dryRun}
            onChange={handleDryRunChange}
            task="year-end statements"
          />
        </>
      }
      action={
        <RunNowButton
          task="year-end statements"
          isRunning={run.isPending}
          disabled={year.trim() === ''}
          onClick={handleRun}
        />
      }
      isRunning={run.isPending}
      result={<StatementsResult run={run} dryRun={lastRunWasDry} />}
    />
  );
}

interface StatementsResultProps {
  run: ReturnType<typeof useRunStatements>;
  dryRun: boolean;
}

/** What the last statement run did, or why it failed; nothing before the first run. */
function StatementsResult({ run, dryRun }: StatementsResultProps): JSX.Element | null {
  if (run.isError) {
    return (
      <p className="field__error" role="alert">
        {run.error instanceof Error ? run.error.message : 'The statement run failed.'}
      </p>
    );
  }
  if (!run.isSuccess) return null;
  const { data } = run;
  if (data.actions.length === 0 && data.sent + data.skipped + data.failed === 0) {
    return <NothingDue dryRun={dryRun} />;
  }
  return (
    <RunActionsTable
      actions={data.actions}
      dryRun={dryRun}
      kindLabel={statementKindLabel}
      summary={<p role="status">{statementsRunSummary(data, dryRun)}</p>}
    />
  );
}
