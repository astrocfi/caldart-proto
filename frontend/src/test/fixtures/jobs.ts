/** Scheduled jobs and their recorded runs, for the System pages' tests. */
import type { JobRun, JobRunDetail, JobStatus } from '@/portal/api/types';

/** A run of the automatic renewal charges the server started, which succeeded. */
export function makeJobRun(overrides: Partial<JobRun> = {}): JobRun {
  return {
    id: 1,
    job: 'renewals',
    name: 'Automatic renewal charges',
    arguments: '',
    started_at: '2026-06-15T13:31:00Z',
    finished_at: '2026-06-15T13:33:05Z',
    outcome: 'succeeded',
    exit_status: 0,
    started_by_name: '',
    error: '',
    ...overrides,
  };
}

/** The same run with its output. */
export function makeJobRunDetail(overrides: Partial<JobRunDetail> = {}): JobRunDetail {
  return {
    ...makeJobRun(),
    output: 'noticed 2, charged 1\n',
    output_truncated: false,
    traceback: '',
    ...overrides,
  };
}

/** One job's state, by default well, with `last_run` as its latest run. */
export function makeJobStatus(overrides: Partial<JobStatus> = {}): JobStatus {
  return {
    job: 'renewals',
    name: 'Automatic renewal charges',
    state: 'ok',
    last_run: makeJobRun(),
    missed_at: null,
    ...overrides,
  };
}
