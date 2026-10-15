/**
 * `/portal/system/jobs/:job`: one scheduled job's recorded runs, newest first, a page
 * at a time: when each started, who started it, how it ended, and how long it took.
 * Each run's time opens its own page, with everything the run wrote.
 */
import type { JSX } from 'react';
import { Link, useParams } from 'react-router-dom';

import { ApiError } from '@/portal/api/client';
import type { JobRun } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import { DataTable } from '@/portal/components/DataTable';
import type { Column } from '@/portal/components/DataTable';
import { DateText } from '@/portal/components/DateText';
import { EmptyState } from '@/portal/components/EmptyState';
import { FilterBar } from '@/portal/components/FilterBar';
import { Page } from '@/portal/components/Page';
import { StatusDot } from '@/portal/components/StatusDot';
import { useUrlFilters } from '@/portal/components/useUrlFilters';
import {
  useFirstPageWhenMissing,
  useUrlListPosition,
} from '@/portal/components/useUrlListPosition';
import type { FilterField, FilterValues } from '@/portal/reports/types';
import { JOB_RUNS_PAGE_SIZE, useJobRuns, useJobs } from './api';
import { FROM_JOB_LOG, OUTCOME, duration, jobRunPath, startedBy } from './jobRuns';

/** The one filter: every run, or the runs that failed or stopped. */
const FILTER_FIELDS: readonly FilterField[] = [
  {
    key: 'outcome',
    label: 'Show',
    kind: 'select',
    placeholder: 'All runs',
    options: [{ value: 'failed', label: 'Failed runs' }],
  },
];
const FILTER_KEYS = FILTER_FIELDS.map((field) => field.key);

/** The server lists a job's runs newest first, whatever the address says. */
const DEFAULT_ORDERING = '-started_at';

/** The jobs whose panel is on Health and database rather than on Scheduled tasks. */
const HEALTH_PAGE_JOBS: ReadonlySet<string> = new Set(['backup', 'registry']);

/** Back to the page that holds the job's panel. */
export function BackToJobs({ job }: { job: string }): JSX.Element {
  return HEALTH_PAGE_JOBS.has(job) ? (
    <Link to="/system/health">Back to health and database</Link>
  ) : (
    <Link to="/system/scheduled">Back to scheduled tasks</Link>
  );
}

/** The run's start opens it; who started it, how it ended, and how long it took follow. */
const COLUMNS: Column<JobRun>[] = [
  {
    key: 'started_at',
    header: 'Started',
    width: '13rem',
    isIdentity: true,
    render: (row) => (
      <Link to={jobRunPath(row.id)} state={{ [FROM_JOB_LOG]: true }}>
        <DateText value={row.started_at} withTime />
      </Link>
    ),
  },
  {
    key: 'started_by',
    header: 'Started by',
    minWidth: '9rem',
    dropOrder: 2,
    render: (row) => startedBy(row),
  },
  {
    key: 'outcome',
    header: 'Outcome',
    width: '8rem',
    keepInSight: true,
    render: (row) => (
      <StatusDot tone={OUTCOME[row.outcome].tone} label={OUTCOME[row.outcome].label} />
    ),
  },
  {
    key: 'duration',
    header: 'Duration',
    width: '7rem',
    numeric: true,
    dropOrder: 3,
    render: (row) => <span className="num">{duration(row)}</span>,
  },
  {
    key: 'error',
    header: 'Error',
    minWidth: '14rem',
    dropOrder: 1,
    render: (row) => (row.error === '' ? '—' : row.error.split('\n', 1)[0]),
  },
];

/** Renders one job's recorded runs, or why they cannot be shown. */
export function JobLogPage(): JSX.Element {
  const job = useParams().job ?? '';
  const [filters, setFilters] = useUrlFilters(FILTER_KEYS);
  const position = useUrlListPosition(DEFAULT_ORDERING);
  const { page, setPage } = position;
  const outcome = filters.outcome ?? '';
  const jobs = useJobs();
  const runs = useJobRuns({ job, page, outcome });
  useFirstPageWhenMissing(position, runs.error);
  const name = jobs.data?.find((row) => row.job === job)?.name ?? 'Scheduled job';
  const back = <BackToJobs job={job} />;

  const handleFilterChange = (next: FilterValues): void => {
    setFilters(next);
  };

  if (runs.isError && page === 1) {
    const isMissing = runs.error instanceof ApiError && runs.error.status === 404;
    return (
      <Page title="Scheduled job" actions={back}>
        <EmptyState
          title={isMissing ? "That isn't a job the server runs" : "The job's runs didn't load"}
          description={isMissing ? undefined : 'Try again in a moment.'}
        />
      </Page>
    );
  }

  const count = runs.data?.count ?? 0;
  return (
    <Page
      title={`${name} log`}
      lede="The runs of the last 90 days, newest first. Open one to read everything it wrote."
      actions={back}
    >
      <Card>
        <DataTable
          singleLine
          columns={COLUMNS}
          rows={runs.data?.results ?? []}
          rowKey={(row) => row.id}
          isLoading={runs.isPending}
          caption={runs.data ? `${count} run${count === 1 ? '' : 's'}` : undefined}
          label={`${name} runs`}
          emptyTitle={outcome === '' ? 'No runs recorded yet' : 'No failed runs'}
          emptyDescription={
            outcome === ''
              ? 'A run is recorded here each time the job runs.'
              : 'Every run of the last 90 days succeeded or is still going.'
          }
          filters={
            <FilterBar
              fields={FILTER_FIELDS}
              values={filters}
              onChange={handleFilterChange}
              label={`Filter ${name} runs`}
              hasReset={false}
            />
          }
          pagination={{
            page,
            pageSize: JOB_RUNS_PAGE_SIZE,
            count,
            onPageChange: setPage,
            label: 'Run pages',
          }}
        />
      </Card>
    </Page>
  );
}
