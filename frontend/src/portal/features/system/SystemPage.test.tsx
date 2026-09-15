import { screen } from '@testing-library/react';
import { HttpResponse, http } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API, makeUser, signedInAs } from '../../../test/handlers';
import { renderWithProviders } from '../../../test/render';
import { server } from '../../../test/server';
import { RequireRole } from '../../auth/guards';
import { SystemPage } from './SystemPage';

const NOW = new Date('2026-06-15T12:00:00Z');

const HEALTH = {
  db: 'ok',
  pending_migrations: 0,
  disk_free_mb: 40_960,
  last_backup: NOW.toISOString(),
  version: '0.1.0',
  debug: false,
};

function systemHandlers() {
  return [
    http.get(`${API}/system/health`, () => HttpResponse.json(HEALTH)),
    http.get(`${API}/system/backups`, () => HttpResponse.json([])),
    http.get(`${API}/admin/reminders/log`, () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
  ];
}

describe('SystemPage', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows the three panels', async () => {
    server.use(...systemHandlers());
    renderWithProviders(<SystemPage />);

    expect(screen.getByRole('heading', { level: 1, name: 'System' })).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Health' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Backups' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Renewal reminders' })).toBeInTheDocument();
  });

  it('renders live data in each panel', async () => {
    server.use(...systemHandlers());
    renderWithProviders(<SystemPage />);

    expect(await screen.findByText('0.1.0')).toBeInTheDocument();
    expect(screen.getByText('No backups yet')).toBeInTheDocument();
    expect(await screen.findByText('No reminders sent yet')).toBeInTheDocument();
  });

  it('is closed to anyone without system_admin', async () => {
    server.use(signedInAs(makeUser({ roles: ['member', 'account_admin'] })));
    renderWithProviders(
      <RequireRole roles={['system_admin']}>
        <SystemPage />
      </RequireRole>,
    );

    expect(await screen.findByText('You do not have access to this page')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Health' })).not.toBeInTheDocument();
  });

  it('is open to a system administrator', async () => {
    server.use(signedInAs(makeUser({ roles: ['member', 'system_admin'] })), ...systemHandlers());
    renderWithProviders(
      <RequireRole roles={['system_admin']}>
        <SystemPage />
      </RequireRole>,
    );

    expect(await screen.findByRole('heading', { name: 'Health' })).toBeInTheDocument();
  });
});
