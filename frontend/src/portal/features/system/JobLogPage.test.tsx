import { screen, within } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeJobRun, makeJobStatus } from '@test/fixtures/jobs';
import { API } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import type { JobRun } from '@/portal/api/types';
import { JobLogPage } from './JobLogPage';

const FAILED = makeJobRun({
  id: 7,
  outcome: 'failed',
  exit_status: 1,
  started_by_name: 'Sam Admin',
  error: '2 renewal charges need checking; settle them on the finance Renewals tab',
});

const SUCCEEDED = makeJobRun({
  id: 6,
  started_at: '2026-06-14T13:31:00Z',
  finished_at: '2026-06-14T13:33:05Z',
});

/** Open the log of `job`, the server answering with `runs`, or a 404 for `null`. */
function renderLog(runs: JobRun[] | null, job = 'renewals'): void {
  server.use(
    http.get(`${API}/system/jobs`, () =>
      HttpResponse.json([
        makeJobStatus(),
        makeJobStatus({ job: 'backup', name: 'Nightly backup' }),
      ]),
    ),
    http.get(`${API}/system/jobs/${job}/runs`, () =>
      runs === null
        ? HttpResponse.json({ detail: 'No such scheduled job.' }, { status: 404 })
        : HttpResponse.json({ count: runs.length, next: null, previous: null, results: runs }),
    ),
  );
  renderRoutes([{ path: '/system/jobs/:job', element: <JobLogPage /> }], {
    route: `/system/jobs/${job}`,
  });
}

describe('JobLogPage', () => {
  it("heads the page with the job's name", async () => {
    renderLog([FAILED]);
    expect(
      await screen.findByRole('heading', { name: 'Automatic renewal charges log' }),
    ).toBeInTheDocument();
  });

  it('lists the runs newest first, as the server sends them', async () => {
    renderLog([FAILED, SUCCEEDED]);
    const table = await screen.findByRole('table');
    await within(table).findByText('Failed');
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((row) => within(row).getByRole('link').getAttribute('href'))).toEqual([
      '/system/jobs/runs/7',
      '/system/jobs/runs/6',
    ]);
  });

  it('names who started a run, and the server for its own', async () => {
    renderLog([FAILED, SUCCEEDED]);
    expect(await screen.findByText('Sam Admin')).toBeInTheDocument();
    expect(screen.getByText('Server')).toBeInTheDocument();
  });

  it('shows how long a run took', async () => {
    renderLog([SUCCEEDED]);
    expect(await screen.findByText('2 min 5 s')).toBeInTheDocument();
  });

  it("shows a failed run's error", async () => {
    renderLog([FAILED]);
    expect(await screen.findByText(FAILED.error)).toBeInTheDocument();
  });

  it('says so when nothing has run yet', async () => {
    renderLog([]);
    expect(await screen.findByText('No runs recorded yet')).toBeInTheDocument();
  });

  it('leads back to the scheduled tasks for a job that has its panel there', async () => {
    renderLog([]);
    expect(await screen.findByRole('link', { name: 'Back to scheduled tasks' })).toHaveAttribute(
      'href',
      '/system/scheduled',
    );
  });

  it('leads back to health and database for the backup', async () => {
    renderLog([], 'backup');
    expect(
      await screen.findByRole('link', { name: 'Back to health and database' }),
    ).toHaveAttribute('href', '/system/health');
  });

  it("says a job the server doesn't run isn't one", async () => {
    renderLog(null, 'nonsense');
    expect(await screen.findByText("That isn't a job the server runs")).toBeInTheDocument();
  });
});
