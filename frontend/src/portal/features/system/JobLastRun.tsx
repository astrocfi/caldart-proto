/**
 * A scheduled job's last recorded run, one line on its panel: when it started, who
 * started it, how it ended, and **View log**, which opens every recent run of the job.
 */
import type { JSX } from 'react';
import { Link } from 'react-router-dom';

import { DateText } from '@/portal/components/DateText';
import { StatusDot } from '@/portal/components/StatusDot';
import { useJobs } from './api';
import { OUTCOME, jobLogPath } from './jobRuns';
import './jobLog.css';

export interface JobLastRunProps {
  /** The job's key, such as `renewals`. */
  job: string;
  /** The words before the run's time, *Last run* unless given, such as *Last nightly backup*. */
  lead?: string;
}

/** The line once the jobs have loaded; null while they load or when they didn't load. */
export function JobLastRun({ job, lead = 'Last run' }: JobLastRunProps): JSX.Element | null {
  const jobs = useJobs();
  const status = jobs.data?.find((row) => row.job === job);
  if (status === undefined) return null;

  const run = status.last_run;
  const link = (
    <Link to={jobLogPath(job)} aria-label={`View log: ${status.name}`}>
      View log
    </Link>
  );
  if (run === null) {
    return (
      <p className="job-last-run muted">
        <span>No run recorded yet.</span>
        {link}
      </p>
    );
  }
  const outcome = OUTCOME[run.outcome];
  return (
    <p className="job-last-run">
      <span className="muted">
        {lead} <DateText value={run.started_at} withTime />
        {run.started_by_name === '' ? '' : `, started by ${run.started_by_name}`}
      </span>
      <StatusDot tone={outcome.tone} label={outcome.label} />
      {link}
    </p>
  );
}
