import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '../../../test/handlers';
import { renderWithProviders } from '../../../test/render';
import { server } from '../../../test/server';
import type { Health } from '../../api/types';
import { HealthPanel, healthChecks } from './HealthPanel';

const NOW = new Date('2026-06-15T12:00:00Z');

/** Yesterday, whenever the suite happens to run: the panel grades against the
 *  real clock, so a hard-coded date would age into a failure. */
const RECENT_BACKUP = new Date(Date.now() - 24 * 3600 * 1000).toISOString();

function health(overrides: Partial<Health> = {}): Health {
  return {
    db: 'ok',
    pending_migrations: 0,
    disk_free_mb: 51_200,
    last_backup: RECENT_BACKUP,
    version: '0.1.0',
    debug: false,
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
    expect(check).toMatchObject({ value: 'never', verdict: 'bad' });
  });

  it('fails when DEBUG is on', () => {
    expect(verdictFor('debug', health({ debug: true }))).toBe('bad');
  });
});

describe('HealthPanel', () => {
  it('renders a row per check with a status chip', async () => {
    server.use(healthHandler(health()));
    renderWithProviders(<HealthPanel />);

    expect(await screen.findByText('Database')).toBeInTheDocument();
    for (const label of ['Pending migrations', 'Disk free', 'Last backup', 'Version', 'Debug mode'])
      expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getAllByText('OK')).toHaveLength(6);
    expect(screen.getByText('0.1.0')).toBeInTheDocument();
  });

  it('flags a problem with the right tone', async () => {
    server.use(healthHandler(health({ debug: true, pending_migrations: 2 })));
    renderWithProviders(<HealthPanel />);

    expect(await screen.findByText('Attention')).toHaveClass('chip--bad');
    expect(screen.getByText('Warning')).toHaveClass('chip--warn');
    expect(screen.getByText('Run manage.py migrate.')).toBeInTheDocument();
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

    await userEvent.click(screen.getByRole('button', { name: 'Refresh' }));

    await waitFor(() => expect(calls).toBe(2));
  });
});
