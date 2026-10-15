/**
 * The words the System pages give a scheduled job's runs: each outcome's dot and word,
 * who started a run, how long it took, and the sentence the health check writes about a
 * job that needs a look.
 */
import type { JobRun, JobRunOutcome, JobStatus } from '@/portal/api/types';
import { formatDate, formatDateTime, formatTime } from '@/portal/components/DateText';
import type { StatusTone } from '@/portal/components/StatusDot';

/** Each outcome's dot and word: green succeeded, red failed or stopped. */
export const OUTCOME: Record<JobRunOutcome, { tone: StatusTone; label: string }> = {
  running: { tone: 'new', label: 'Running' },
  succeeded: { tone: 'current', label: 'Succeeded' },
  failed: { tone: 'expired', label: 'Failed' },
  stopped: { tone: 'expired', label: 'Stopped' },
};

/**
 * The key a run opened from a job's log sets in the history state, so the run's page
 * knows the log, with its page and filter, is one step back.
 */
export const FROM_JOB_LOG = 'fromJobLog';

/** Where each job's log is. */
export function jobLogPath(job: string): string {
  return `/system/jobs/${encodeURIComponent(job)}`;
}

/** Where one run's record is. */
export function jobRunPath(id: number): string {
  return `/system/jobs/runs/${id}`;
}

/** Who started a run: the administrator who pressed **Run now**, or the server. */
export function startedBy(run: JobRun): string {
  return run.started_by_name === '' ? 'Server' : run.started_by_name;
}

/** How long a run took, such as *45 s*, *2 min 5 s*, or *1 h 3 min*; a dash while it runs. */
export function duration(run: JobRun): string {
  if (run.finished_at === null) return '—';
  const seconds = Math.max(
    0,
    Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000),
  );
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ${seconds % 60} s`;
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

/** *at 6:30 AM* for a moment on `now`'s Pacific day, *on 10/14/2026 at 6:30 AM* otherwise. */
function when(iso: string, now: Date): string {
  return formatDate(iso) === formatDate(now.toISOString())
    ? `at ${formatTime(iso)}`
    : `on ${formatDateTime(iso)}`;
}

/** The first line of a run's error, which for a traceback's summary is the whole of it. */
function firstLine(text: string): string {
  return text.split('\n', 1)[0]?.trim() ?? '';
}

/**
 * What the health check says about `status`, such as *Automatic renewal charges failed
 * at 6:30 AM: 2 renewal charges need checking*; `null` for a job that is well.
 */
export function jobTrouble(status: JobStatus, now: Date = new Date()): string | null {
  const { name, state, last_run: run, missed_at: missedAt } = status;
  if (state === 'failed' && run !== null) {
    const reason = firstLine(run.error);
    const at = when(run.finished_at ?? run.started_at, now);
    return reason === '' ? `${name} failed ${at}.` : `${name} failed ${at}: ${reason}`;
  }
  if (state === 'stopped' && run !== null) {
    return `${name}: the run that started ${when(run.started_at, now)} stopped before it finished.`;
  }
  if (state === 'overdue' && missedAt !== null) {
    return `${name}: due ${when(missedAt, now)}, without a run since.`;
  }
  if (state === 'never_run' && missedAt !== null) {
    return `${name}: due ${when(missedAt, now)}, and still waiting for its first run.`;
  }
  return null;
}

/** Whether `status` is a problem (a failed or stopped run) rather than a late one. */
export function isJobProblem(status: JobStatus): boolean {
  return status.state === 'failed' || status.state === 'stopped';
}

/** Whether `status` is late: overdue, or never run though it was due. */
export function isJobLate(status: JobStatus): boolean {
  return status.state === 'overdue' || status.state === 'never_run';
}
