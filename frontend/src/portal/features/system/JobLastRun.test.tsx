import { screen } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { makeJobRun, makeJobStatus } from '@test/fixtures/jobs';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { JobStatus } from '@/portal/api/types';
import { JobLastRun } from './JobLastRun';

/** Answer `GET /system/jobs` with `jobs`. */
function answerJobs(...jobs: JobStatus[]): void {
  server.use(http.get(`${API}/system/jobs`, () => HttpResponse.json(jobs)));
}

describe('JobLastRun', () => {
  it("links to the job's log", async () => {
    answerJobs(makeJobStatus());
    renderWithProviders(<JobLastRun job="renewals" />);
    expect(
      await screen.findByRole('link', { name: 'View log: Automatic renewal charges' }),
    ).toHaveAttribute('href', '/system/jobs/renewals');
  });

  it('reads when the last run started', async () => {
    answerJobs(makeJobStatus());
    renderWithProviders(<JobLastRun job="renewals" />);
    expect(await screen.findByText('06/15/2026 at 6:31 AM')).toBeInTheDocument();
  });

  it('reads how the last run ended', async () => {
    answerJobs(makeJobStatus({ last_run: makeJobRun({ outcome: 'failed' }) }));
    renderWithProviders(<JobLastRun job="renewals" />);
    expect(await screen.findByText('Failed')).toBeInTheDocument();
  });

  it('names the administrator who started the last run', async () => {
    answerJobs(makeJobStatus({ last_run: makeJobRun({ started_by_name: 'Sam Admin' }) }));
    renderWithProviders(<JobLastRun job="renewals" />);
    expect(await screen.findByText(/started by Sam Admin/)).toBeInTheDocument();
  });

  it('takes the words a panel gives it', async () => {
    answerJobs(makeJobStatus({ job: 'backup', name: 'Nightly backup' }));
    renderWithProviders(<JobLastRun job="backup" lead="Last nightly backup" />);
    expect(await screen.findByText(/Last nightly backup/)).toBeInTheDocument();
  });

  it('says so when no run is recorded yet', async () => {
    answerJobs(makeJobStatus({ state: 'waiting', last_run: null }));
    renderWithProviders(<JobLastRun job="renewals" />);
    expect(await screen.findByText('No run recorded yet.')).toBeInTheDocument();
  });
});
