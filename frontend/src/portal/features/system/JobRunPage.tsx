/**
 * `/portal/system/jobs/runs/:id`: one recorded run of a scheduled job on a page of its
 * own: when it ran, who started it, how it ended, its error, and everything it wrote, in
 * a monospace block as the server's terminal shows it.
 */
import type { JSX, MouseEvent, ReactNode } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { JobRunDetail } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import { DateText } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusDot';
import { useJobRun } from './api';
import { FROM_JOB_LOG, OUTCOME, duration, jobLogPath, startedBy } from './jobRuns';
import './jobLog.css';

/** How much of a run's output the server keeps, its tail, in KB (65,536 characters). */
export const OUTPUT_LIMIT_KB = 64;

interface BackToLogProps {
  job: string;
  name: string;
}

/**
 * **Back to the … log**: the log with its page and filter as they were, when the log is
 * where the run was opened from; the log's first page otherwise, such as for a link
 * from a panel or the health check.
 */
function BackToLog({ job, name }: BackToLogProps): JSX.Element {
  const location = useLocation();
  const navigate = useNavigate();
  const isFromLog = (location.state as Record<string, unknown> | null)?.[FROM_JOB_LOG] === true;
  const handleClick = (event: MouseEvent<HTMLAnchorElement>): void => {
    if (!isFromLog) return;
    event.preventDefault();
    void navigate(-1);
  };
  return (
    <Link to={jobLogPath(job)} onClick={handleClick}>
      Back to the {name} log
    </Link>
  );
}

/** Renders one recorded run, or why it cannot be shown. */
export function JobRunPage(): JSX.Element {
  const id = Number(useParams().id);
  const run = useJobRun(id);

  if (run.isError) {
    const isMissing = run.error instanceof ApiError && run.error.status === 404;
    return (
      <Page title="Job run" actions={<Link to="/system/scheduled">Back to scheduled tasks</Link>}>
        <EmptyState
          title={isMissing ? "That run isn't in the record" : "That run didn't load"}
          description={
            isMissing ? 'The site keeps the runs of the last 90 days.' : 'Try again in a moment.'
          }
        />
      </Page>
    );
  }

  if (run.data === undefined) {
    return (
      <Page title="Job run">
        <p className="muted" role="status">
          Loading the run…
        </p>
      </Page>
    );
  }

  const back = <BackToLog job={run.data.job} name={run.data.name} />;
  return (
    <Page title={`${run.data.name} run`} actions={back}>
      <RunCard run={run.data} />
    </Page>
  );
}

/** The run's facts, one line each, then its error, its output, and its traceback. */
function RunCard({ run }: { run: JobRunDetail }): JSX.Element {
  const outcome = OUTCOME[run.outcome];
  const facts: [string, ReactNode][] = [
    ['Started', <DateText key="started" value={run.started_at} withTime />],
    ['Finished', <DateText key="finished" value={run.finished_at} withTime />],
    ['Duration', duration(run)],
    ['Started by', startedBy(run)],
    ['Outcome', <StatusDot key="outcome" tone={outcome.tone} label={outcome.label} />],
  ];
  if (run.exit_status !== null) facts.push(['Exit status', String(run.exit_status)]);
  if (run.arguments !== '') {
    facts.push(['Options', <code key="options">{run.arguments}</code>]);
  }
  if (run.error !== '') facts.push(['Error', run.error]);

  return (
    <Card>
      <dl className="job-run__facts">
        {facts.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <h2 className="job-run__heading">Output</h2>
      {run.output_truncated ? (
        <p className="muted">
          The run wrote more than {OUTPUT_LIMIT_KB} KB, so only its last {OUTPUT_LIMIT_KB} KB are
          kept. The server&apos;s own log has all of it.
        </p>
      ) : null}
      {run.output === '' ? (
        <p className="muted">The run didn&apos;t write anything.</p>
      ) : (
        <pre className="job-run__output mono">{run.output}</pre>
      )}
      {run.traceback === '' ? null : (
        <>
          <h2 className="job-run__heading">Traceback</h2>
          <pre className="job-run__output mono">{run.traceback}</pre>
        </>
      )}
    </Card>
  );
}
