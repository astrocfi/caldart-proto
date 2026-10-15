import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { makeJobRun, makeJobStatus } from '@test/fixtures/jobs';
import type { Health } from '@/portal/api/types';
import { HealthPanel, healthChecks } from './HealthPanel';

const NOW = new Date('2026-06-15T12:00:00Z');

/** One day before `NOW`. `HealthPanel` itself grades against the pinned system
 *  clock, so every fixture date is derived from `NOW` rather than the real clock. */
const RECENT_BACKUP = new Date(NOW.getTime() - 24 * 3600 * 1000).toISOString();

function health(overrides: Partial<Health> = {}): Health {
  return {
    db: 'ok',
    pending_migrations: 0,
    disk_free_mb: 51_200,
    last_backup: RECENT_BACKUP,
    version: '0.1.0',
    debug: false,
    scheduled_jobs: [],
    ...overrides,
  };
}

function healthHandler(payload: Health) {
  return http.get(`${API}/system/health`, () => HttpResponse.json(payload));
}

function verdictFor(key: string, payload: Health): string {
  return healthChecks(payload, NOW).find((check) => check.key === key)!.verdict;
}

describe('healthChecks', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('passes a healthy box', () => {
    expect(healthChecks(health(), NOW).every((check) => check.verdict === 'ok')).toBe(true);
  });

  it('fails on a database error', () => {
    expect(verdictFor('db', health({ db: 'error: connection refused' }))).toBe('bad');
  });

  it('warns about unapplied migrations', () => {
    expect(verdictFor('pending_migrations', health({ pending_migrations: 3 }))).toBe('warn');
  });

  it('grades the free disk space', () => {
    expect(verdictFor('disk_free_mb', health({ disk_free_mb: 4096 }))).toBe('ok');
    expect(verdictFor('disk_free_mb', health({ disk_free_mb: 1024 }))).toBe('warn');
    expect(verdictFor('disk_free_mb', health({ disk_free_mb: 100 }))).toBe('bad');
  });

  it('grades the age of the last backup', () => {
    expect(verdictFor('last_backup', health({ last_backup: '2026-06-10T09:00:00Z' }))).toBe('ok');
    expect(verdictFor('last_backup', health({ last_backup: '2026-06-01T09:00:00Z' }))).toBe('warn');
    expect(verdictFor('last_backup', health({ last_backup: '2026-01-01T09:00:00Z' }))).toBe('bad');
  });

  it('treats never having backed up as bad', () => {
    const check = healthChecks(health({ last_backup: null }), NOW).find(
      (row) => row.key === 'last_backup',
    );
    expect(check).toMatchObject({ value: 'No backup yet', verdict: 'bad' });
  });

  it('fails when DEBUG is on', () => {
    expect(verdictFor('debug', health({ debug: true }))).toBe('bad');
  });

  /** The value and the note `key` reads in, for `payload`. */
  function wordsFor(key: string, payload: Health): [string, string | undefined] {
    const check = healthChecks(payload, NOW).find((row) => row.key === key)!;
    return [check.value, check.note];
  }

  it.each([
    ['db', health(), 'Connected'],
    ['db', health({ db: 'error: connection refused' }), 'Not reachable'],
    ['pending_migrations', health(), 'Complete'],
    ['pending_migrations', health({ pending_migrations: 3 }), '3 steps not applied'],
    ['pending_migrations', health({ pending_migrations: 1 }), '1 step not applied'],
    ['disk_free_mb', health({ disk_free_mb: 51_200 }), '50.0 GB'],
    ['disk_free_mb', health({ disk_free_mb: 512 }), '512 MB'],
    ['debug', health(), 'Off'],
    ['debug', health({ debug: true }), 'On'],
  ])('reads %s in plain words: %#', (key, payload, value) => {
    expect(wordsFor(key, payload)[0]).toBe(value);
  });

  it('tells the reader who to ask, never which command to run', () => {
    const notes = healthChecks(
      health({ db: 'error: down', pending_migrations: 2, debug: true, last_backup: null }),
      NOW,
    ).map((check) => check.note ?? '');
    expect(notes.join(' ')).not.toMatch(/manage\.py|DEBUG|BACKUP_DIR|dump/);
    expect(notes.filter((note) => note.includes('the person who installed the site'))).toHaveLength(
      3,
    );
  });
});

describe('the scheduled jobs check', () => {
  /** A renewal run that failed at 6:30 AM Pacific on `NOW`'s day. */
  const FAILED = makeJobStatus({
    state: 'failed',
    last_run: makeJobRun({
      outcome: 'failed',
      exit_status: 1,
      finished_at: '2026-06-15T13:30:00Z',
      error: '2 renewal charges need checking; settle them on the finance Renewals tab',
    }),
  });

  /** The bounce check, due at 4:20 AM Pacific and not run since. */
  const OVERDUE = makeJobStatus({
    job: 'bounces',
    name: 'Bounce check',
    state: 'overdue',
    missed_at: '2026-06-15T11:20:00Z',
  });

  function jobsCheck(payload: Health) {
    return healthChecks(payload, NOW).find((check) => check.key === 'scheduled_jobs')!;
  }

  it('reads on schedule when every job is well', () => {
    expect(jobsCheck(health({ scheduled_jobs: [makeJobStatus()] }))).toMatchObject({
      value: 'On schedule',
      verdict: 'ok',
    });
  });

  it('is a problem when a job failed', () => {
    expect(jobsCheck(health({ scheduled_jobs: [FAILED] })).verdict).toBe('bad');
  });

  it('names the failed job, when it failed, and why', () => {
    expect(jobsCheck(health({ scheduled_jobs: [FAILED] })).jobs).toEqual([
      {
        job: 'renewals',
        text: 'Automatic renewal charges failed at 6:30 AM: 2 renewal charges need checking; settle them on the finance Renewals tab',
      },
    ]);
  });

  it('dates a failure from another day', () => {
    const yesterday = makeJobStatus({
      state: 'failed',
      last_run: makeJobRun({ outcome: 'failed', finished_at: '2026-06-14T13:30:00Z', error: '' }),
    });
    expect(jobsCheck(health({ scheduled_jobs: [yesterday] })).jobs?.[0]?.text).toBe(
      'Automatic renewal charges failed on 06/14/2026 at 6:30 AM.',
    );
  });

  it('is a problem when a run stopped before it finished', () => {
    const stopped = makeJobStatus({
      state: 'stopped',
      last_run: makeJobRun({ outcome: 'stopped', finished_at: null, exit_status: null }),
    });
    expect(jobsCheck(health({ scheduled_jobs: [stopped] })).jobs?.[0]?.text).toBe(
      'Automatic renewal charges: the run that started at 6:31 AM stopped before it finished.',
    );
  });

  it('warns about a late job, naming when it was due', () => {
    const check = jobsCheck(health({ scheduled_jobs: [OVERDUE] }));
    expect(check).toMatchObject({
      verdict: 'warn',
      value: '1 late',
      jobs: [{ job: 'bounces', text: 'Bounce check: due at 4:20 AM, without a run since.' }],
    });
  });

  it('warns about a job that has never run though it was due', () => {
    const never = makeJobStatus({
      state: 'never_run',
      last_run: null,
      missed_at: '2026-06-15T13:30:00Z',
    });
    expect(jobsCheck(health({ scheduled_jobs: [never] })).jobs?.[0]?.text).toBe(
      'Automatic renewal charges: due at 6:30 AM, and still waiting for its first run.',
    );
  });

  it('counts failures and late jobs together, failures first', () => {
    expect(jobsCheck(health({ scheduled_jobs: [OVERDUE, FAILED] }))).toMatchObject({
      value: '1 failed, 1 late',
      verdict: 'bad',
    });
  });

  it('reads a job that is waiting for its first run as well', () => {
    const waiting = makeJobStatus({ state: 'waiting', last_run: null });
    expect(jobsCheck(health({ scheduled_jobs: [waiting] })).verdict).toBe('ok');
  });

  it('cannot judge the jobs while their record is unreadable', () => {
    expect(jobsCheck(health({ scheduled_jobs: null }))).toMatchObject({
      value: 'Unknown',
      verdict: 'warn',
    });
  });

  it('cannot judge the jobs while the database is down', () => {
    expect(jobsCheck(health({ db: 'error: down' }))).toMatchObject({
      value: 'Unknown',
      verdict: 'warn',
    });
  });
});

describe('HealthPanel', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders a row per check with its status', async () => {
    server.use(healthHandler(health()));
    renderWithProviders(<HealthPanel />);

    expect(await screen.findByText('Database')).toBeInTheDocument();
    for (const label of [
      'Database upgrade',
      'Disk free',
      'Last backup',
      'Scheduled jobs',
      'Version',
      'Debug mode',
    ])
      expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getAllByText('Good')).toHaveLength(7);
    expect(screen.getByText('0.1.0')).toBeInTheDocument();
  });

  it('flags a problem with the right tone', async () => {
    server.use(healthHandler(health({ debug: true, pending_migrations: 2 })));
    renderWithProviders(<HealthPanel />);

    expect(await screen.findByText('Problem')).toHaveAttribute('data-tone', 'expired');
    expect(screen.getByText('Warning')).toHaveAttribute('data-tone', 'expiring');
    expect(
      screen.getByText(
        'An upgrade was left half finished. Tell the person who installed the site.',
      ),
    ).toBeInTheDocument();
  });

  it('links a failed job to its log', async () => {
    server.use(
      healthHandler(
        health({
          scheduled_jobs: [
            makeJobStatus({ state: 'failed', last_run: makeJobRun({ outcome: 'failed' }) }),
          ],
        }),
      ),
    );
    renderWithProviders(<HealthPanel />);

    expect(await screen.findByRole('link', { name: 'View log' })).toHaveAttribute(
      'href',
      '/system/jobs/renewals',
    );
  });

  it('shows the error when the check itself fails', async () => {
    server.use(
      http.get(`${API}/system/health`, () =>
        HttpResponse.json({ detail: 'Server error' }, { status: 500 }),
      ),
    );
    renderWithProviders(<HealthPanel />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Server error');
  });

  it('refetches on demand', async () => {
    let calls = 0;
    server.use(
      http.get(`${API}/system/health`, () => {
        calls += 1;
        return HttpResponse.json(health());
      }),
    );
    renderWithProviders(<HealthPanel />);
    await screen.findByText('Database');

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await user.click(screen.getByRole('button', { name: 'Refresh' }));

    await waitFor(() => expect(calls).toBe(2));
  });
});
