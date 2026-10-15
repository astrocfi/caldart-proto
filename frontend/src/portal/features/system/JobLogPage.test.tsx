import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeJobRun, makeJobRunDetail, makeJobStatus } from '@test/fixtures/jobs';
import { API } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import type { JobRun } from '@/portal/api/types';
import { JobLogPage } from './JobLogPage';
import { JobRunPage } from './JobRunPage';

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

/** The query strings the runs list was asked for, in order. */
let asked: string[] = [];

/** Open the log of `job`, the server answering with `runs`, or a 404 for `null`. */
function renderLog(runs: JobRun[] | null, job = 'renewals', route = `/system/jobs/${job}`) {
  asked = [];
  server.use(
    http.get(`${API}/system/jobs`, () =>
      HttpResponse.json([
        makeJobStatus(),
        makeJobStatus({ job: 'backup', name: 'Nightly backup' }),
      ]),
    ),
    http.get(`${API}/system/jobs/${job}/runs`, ({ request }) => {
      asked.push(new URL(request.url).search);
      return runs === null
        ? HttpResponse.json({ detail: 'No such scheduled job.' }, { status: 404 })
        : HttpResponse.json({
            count: runs.length === 0 ? 0 : 60,
            next: null,
            previous: null,
            results: runs,
          });
    }),
  );
  return renderRoutes([{ path: '/system/jobs/:job', element: <JobLogPage /> }], { route });
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

  it('asks for the page the address names', async () => {
    renderLog([FAILED], 'renewals', '/system/jobs/renewals?page=2');
    await screen.findByText(FAILED.error);
    expect(asked).toContain('?page=2');
  });

  it('keeps the page in the address when moving to the next one', async () => {
    const { router } = renderLog([FAILED]);
    await screen.findByText(FAILED.error);
    await userEvent.click(screen.getByRole('button', { name: /Next/ }));
    expect(router.state.location.search).toBe('?page=2');
  });

  it('asks for the failed runs alone when the filter says so', async () => {
    renderLog([FAILED], 'renewals', '/system/jobs/renewals?outcome=failed');
    await screen.findByText(FAILED.error);
    expect(asked).toContain('?outcome=failed');
  });

  it('puts the filter in the address when it is chosen', async () => {
    const { router } = renderLog([FAILED]);
    await screen.findByText(FAILED.error);
    await userEvent.selectOptions(screen.getByLabelText('Show'), 'failed');
    expect(router.state.location.search).toBe('?outcome=failed');
  });

  it("says so when none of the job's runs failed", async () => {
    renderLog([], 'renewals', '/system/jobs/renewals?outcome=failed');
    expect(await screen.findByText('No failed runs')).toBeInTheDocument();
  });

  it('returns from a run to the same page of the log', async () => {
    server.use(
      http.get(`${API}/system/jobs/runs/7`, () =>
        HttpResponse.json(makeJobRunDetail({ id: 7, outcome: 'failed' })),
      ),
    );
    const { router } = renderLogAndRun('/system/jobs/renewals?page=2');
    await userEvent.click(await screen.findByRole('link', { name: '06/15/2026 at 6:31 AM' }));
    await userEvent.click(
      await screen.findByRole('link', { name: 'Back to the Automatic renewal charges log' }),
    );
    expect(`${router.state.location.pathname}${router.state.location.search}`).toBe(
      '/system/jobs/renewals?page=2',
    );
  });
});

/** Open the log at `route` with the run's own page routed too. */
function renderLogAndRun(route: string) {
  server.use(
    http.get(`${API}/system/jobs`, () => HttpResponse.json([makeJobStatus()])),
    http.get(`${API}/system/jobs/renewals/runs`, () =>
      HttpResponse.json({ count: 60, next: null, previous: null, results: [FAILED] }),
    ),
  );
  return renderRoutes(
    [
      { path: '/system/jobs/:job', element: <JobLogPage /> },
      { path: '/system/jobs/runs/:id', element: <JobRunPage /> },
    ],
    { route },
  );
}
