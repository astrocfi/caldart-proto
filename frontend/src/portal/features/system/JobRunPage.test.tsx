import { screen } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeJobRunDetail } from '@test/fixtures/jobs';
import { API } from '@test/handlers';
import { renderRoutes } from '@test/render';
import { server } from '@test/server';
import type { JobRunDetail } from '@/portal/api/types';
import { JobRunPage } from './JobRunPage';

/** Open run 7, the server answering with `run`, or a 404 for `null`. */
function renderRun(run: JobRunDetail | null): void {
  server.use(
    http.get(`${API}/system/jobs/runs/7`, () =>
      run === null
        ? HttpResponse.json({ detail: 'Not found.' }, { status: 404 })
        : HttpResponse.json(run),
    ),
  );
  renderRoutes([{ path: '/system/jobs/runs/:id', element: <JobRunPage /> }], {
    route: '/system/jobs/runs/7',
  });
}

const FAILED = makeJobRunDetail({
  id: 7,
  outcome: 'failed',
  exit_status: 1,
  arguments: '--scan-id 4',
  output: 'noticed 2, charged 1\nCommandError follows\n',
  error: '2 renewal charges need checking',
});

describe('JobRunPage', () => {
  it("heads the page with the job's name", async () => {
    renderRun(FAILED);
    expect(
      await screen.findByRole('heading', { name: 'Automatic renewal charges run' }),
    ).toBeInTheDocument();
  });

  it('shows the whole output in a monospace block', async () => {
    renderRun(FAILED);
    const output = await screen.findByText(/noticed 2, charged 1/);
    expect(output.tagName).toBe('PRE');
  });

  it('keeps the output exactly as written, line breaks and all', async () => {
    renderRun(FAILED);
    const output = await screen.findByText(/noticed 2, charged 1/);
    expect(output.textContent).toBe(FAILED.output);
  });

  it("names the run's outcome, exit status, and error", async () => {
    renderRun(FAILED);
    expect(await screen.findByText('Failed')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2 renewal charges need checking')).toBeInTheDocument();
  });

  it('shows the options the command was given', async () => {
    renderRun(FAILED);
    expect(await screen.findByText('--scan-id 4')).toBeInTheDocument();
  });

  it('says when only the tail of the output was kept', async () => {
    renderRun(makeJobRunDetail({ output_truncated: true }));
    expect(await screen.findByText(/only its last 64 KB are kept/)).toBeInTheDocument();
  });

  it('shows a traceback under its own heading', async () => {
    renderRun(makeJobRunDetail({ traceback: 'Traceback (most recent call last):\n  boom\n' }));
    expect(await screen.findByRole('heading', { name: 'Traceback' })).toBeInTheDocument();
  });

  it("leads back to the job's log", async () => {
    renderRun(FAILED);
    expect(
      await screen.findByRole('link', { name: 'Back to the Automatic renewal charges log' }),
    ).toHaveAttribute('href', '/system/jobs/renewals');
  });

  it('says so when the run has been pruned', async () => {
    renderRun(null);
    expect(await screen.findByText("That run isn't in the record")).toBeInTheDocument();
  });
});
