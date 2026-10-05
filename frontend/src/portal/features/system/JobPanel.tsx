/**
 * One scheduled job's panel on `/portal/system/scheduled`, laid out the same way for
 * every job: what the job does and when the server runs it, a line when the job cannot
 * run, the fields that shape a run (a year, the practice run box), **Run now**, what the
 * last run did, and then anything more the job keeps, such as its log.
 *
 * The result sits below **Run now**, so the button never moves when a long result
 * appears, and when a run ends the focus moves to the result's heading (or to its
 * failure), so a keyboard or screen reader user lands on what the run did.
 */
import type { JSX, ReactNode } from 'react';

import { Button } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { actionsHeading } from '@/portal/components/RunActionsTable';
import { useFocusRunResult } from '@/portal/components/focus';
import './jobPanel.css';

export interface JobPanelProps {
  eyebrow: string;
  title: string;
  /** What the job does and when the server runs it, naming the job. */
  description: ReactNode;
  /** A line before the controls, such as why the job cannot run here. */
  notice?: ReactNode;
  /** The fields that shape a run, before **Run now**: a year, the practice run box. */
  options?: ReactNode;
  /** **Run now**: a `RunNowButton`, or a `ConfirmButton` for a run that asks first. */
  action: ReactNode;
  /** Whether a run is in flight; the focus moves to the result when one ends. */
  isRunning: boolean;
  /** What the last run did, or why it failed, below **Run now**. */
  result?: ReactNode;
  /** More below the result, such as the job's log under its own heading. */
  children?: ReactNode;
}

/** A scheduled job's description, controls, result, and anything more, in that order. */
export function JobPanel({
  eyebrow,
  title,
  description,
  notice,
  options,
  action,
  isRunning,
  result,
  children,
}: JobPanelProps): JSX.Element {
  const resultRef = useFocusRunResult(isRunning);

  return (
    <Card eyebrow={eyebrow} title={title} className="job-panel">
      <p className="muted">{description}</p>
      {notice}
      {options === undefined ? null : <div className="job-panel__options">{options}</div>}
      <div className="cluster job-panel__run">{action}</div>
      <div ref={resultRef} className="job-panel__result">
        {result}
      </div>
      {children}
    </Card>
  );
}

export interface RunNowButtonProps {
  /** The job, heard after *Run now*, since the page holds several. */
  task: string;
  isRunning: boolean;
  /** Hold the button back, such as while the job has nothing set up to run. */
  disabled?: boolean;
  onClick: () => void;
}

/** **Run now**, named for its job, reading *Running…* and held back while it runs. */
export function RunNowButton({
  task,
  isRunning,
  disabled = false,
  onClick: handleClick,
}: RunNowButtonProps): JSX.Element {
  return (
    <Button
      onClick={handleClick}
      disabled={isRunning || disabled}
      aria-label={isRunning ? undefined : `Run now: ${task}`}
    >
      {isRunning ? 'Running…' : 'Run now'}
    </Button>
  );
}

export interface NothingDueProps {
  /** Whether the run was a practice run, which reads in the present tense. */
  dryRun: boolean;
}

/** A run that found nothing at all to do: its heading and one line, and no table. */
export function NothingDue({ dryRun }: NothingDueProps): JSX.Element {
  return (
    <div className="run-actions stack-tight">
      <h3>{actionsHeading(dryRun)}</h3>
      <p role="status">{dryRun ? 'Nothing is due.' : 'Nothing was due.'}</p>
    </div>
  );
}
