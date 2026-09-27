import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { makeRegistryImport, makeRegistryStatus } from '@test/fixtures/registry';
import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { RegistryStatus } from '@/portal/api/types';
import { REGISTRY_POLL_MS } from '@/portal/api/queries';
import { RegistryPanel, registryImportSummary } from './RegistryPanel';

const STARTED = '2026-09-27T11:05:00Z';

/** The status of an import that started at `STARTED` and has not finished. */
function running(): RegistryStatus {
  return makeRegistryStatus({
    running: true,
    last: makeRegistryImport({ started_at: STARTED, finished_at: null }),
  });
}

/** `STARTED` on the reader's own clock, as the panel prints it. */
function startedClock(): string {
  const at = new Date(STARTED);
  return `${String(at.getHours()).padStart(2, '0')}:${String(at.getMinutes()).padStart(2, '0')}`;
}

/** Answer `GET /aircraft/registry` with each of `answers` in turn, the last one after that. */
function statusAnswers(...answers: RegistryStatus[]) {
  let asked = 0;
  return http.get(`${API}/aircraft/registry`, () => {
    const answer = answers[Math.min(asked, answers.length - 1)];
    asked += 1;
    return HttpResponse.json(answer);
  });
}

describe('registryImportSummary', () => {
  it('counts what the last import wrote and names its day', () => {
    expect(registryImportSummary(makeRegistryStatus())).toBe(
      'Imported 312 types and 204 registrations on 2026/09/20.',
    );
  });

  it('adds the hand-added types the import folded in', () => {
    const status = makeRegistryStatus({ last: makeRegistryImport({ types_folded: 2 }) });
    expect(registryImportSummary(status)).toBe(
      'Imported 312 types and 204 registrations on 2026/09/20, folded 2 hand-added types.',
    );
  });

  it('writes one of each in the singular', () => {
    const status = makeRegistryStatus({
      last: makeRegistryImport({ types_written: 1, registrations_written: 1, types_folded: 1 }),
    });
    expect(registryImportSummary(status)).toBe(
      'Imported 1 type and 1 registration on 2026/09/20, folded 1 hand-added type.',
    );
  });

  it('gives the error of a failed import', () => {
    const status = makeRegistryStatus({
      as_of: null,
      last: makeRegistryImport({ ok: false, error: 'Did not finish.' }),
    });
    expect(registryImportSummary(status)).toBe('Failed: Did not finish.');
  });

  it('says when a running import started', () => {
    expect(registryImportSummary(running())).toBe(`Running since ${startedClock()}`);
  });

  it('says so when no import has ever run', () => {
    expect(registryImportSummary(makeRegistryStatus({ as_of: null, last: null }))).toBe(
      'No import has run yet.',
    );
  });
});

describe('<RegistryPanel/>', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('is the FAA registry import, with Run now and no dry run', async () => {
    server.use(statusAnswers(makeRegistryStatus()));
    renderWithProviders(<RegistryPanel />);
    expect(await screen.findByRole('heading', { name: 'FAA registry import' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Run now' })).toBeVisible();
    expect(screen.queryByRole('checkbox')).toBeNull();
  });

  it('reads the last import as it mounts', async () => {
    server.use(statusAnswers(makeRegistryStatus()));
    renderWithProviders(<RegistryPanel />);
    expect(
      await screen.findByText('Imported 312 types and 204 registrations on 2026/09/20.'),
    ).toBeVisible();
  });

  it('starts an import on Run now and shows it running', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    let posts = 0;
    server.use(
      statusAnswers(makeRegistryStatus(), running()),
      http.post(`${API}/admin/system/registry-import`, () => {
        posts += 1;
        return HttpResponse.json(running().last, { status: 202 });
      }),
    );
    renderWithProviders(<RegistryPanel />);
    await screen.findByText(/^Imported/);
    await user.click(screen.getByRole('button', { name: 'Run now' }));
    expect(await screen.findByText(`Running since ${startedClock()}`)).toBeVisible();
    expect(posts).toBe(1);
  });

  it('holds Run now down while an import runs', async () => {
    server.use(statusAnswers(running()));
    renderWithProviders(<RegistryPanel />);
    await screen.findByText(/^Running since/);
    expect(screen.getByRole('button', { name: 'Running…' })).toBeDisabled();
  });

  it('asks again every five seconds while an import runs, and shows how it ended', async () => {
    server.use(statusAnswers(running(), makeRegistryStatus()));
    renderWithProviders(<RegistryPanel />);
    await screen.findByText(/^Running since/);
    await act(() => vi.advanceTimersByTimeAsync(REGISTRY_POLL_MS));
    expect(await screen.findByText(/^Imported 312 types/)).toBeVisible();
  });

  it('stops asking once no import is running', async () => {
    let asked = 0;
    server.use(
      http.get(`${API}/aircraft/registry`, () => {
        asked += 1;
        return HttpResponse.json(makeRegistryStatus());
      }),
    );
    renderWithProviders(<RegistryPanel />);
    await screen.findByText(/^Imported/);
    await act(() => vi.advanceTimersByTimeAsync(REGISTRY_POLL_MS * 3));
    expect(asked).toBe(1);
  });

  it('says so when an import is already running on the server', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    server.use(
      statusAnswers(makeRegistryStatus()),
      http.post(`${API}/admin/system/registry-import`, () =>
        HttpResponse.json({ detail: 'An import is already running.' }, { status: 409 }),
      ),
    );
    renderWithProviders(<RegistryPanel />);
    await screen.findByText(/^Imported/);
    await user.click(screen.getByRole('button', { name: 'Run now' }));
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('An import is already running.'),
    );
  });
});
