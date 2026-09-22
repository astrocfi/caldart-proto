import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, delay, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import type { Backup } from '@/portal/api/types';
import { BackupsPanel, formatBytes } from './BackupsPanel';

const BACKUPS: Backup[] = [
  {
    name: 'caldart-20260601-070000.sql.gz',
    size_bytes: 2_411_724,
    created_at: '2026-06-01T07:00:00Z',
  },
  {
    name: 'caldart-20260515-070000.sql.gz',
    size_bytes: 2_310_000,
    created_at: '2026-05-15T07:00:00Z',
  },
];

function listHandler(rows: Backup[]) {
  return http.get(`${API}/system/backups`, () => HttpResponse.json(rows));
}

describe('formatBytes', () => {
  it('scales to the right unit', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(2048)).toBe('2.0 kB');
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB');
    expect(formatBytes(3 * 1024 * 1024 * 1024)).toBe('3.00 GB');
  });
});

describe('BackupsPanel', () => {
  it('lists what is on disk with a download link each', async () => {
    server.use(listHandler(BACKUPS));
    renderWithProviders(<BackupsPanel />);

    expect(await screen.findByText(BACKUPS[0]!.name)).toBeInTheDocument();
    expect(screen.getByText('2.3 MB')).toBeInTheDocument();
    const links = screen.getAllByRole('link', { name: 'Download' });
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute('href', `/api/v1/system/backups/${BACKUPS[0]!.name}/download`);
  });

  it('shows an empty state when there are none', async () => {
    server.use(listHandler([]));
    renderWithProviders(<BackupsPanel />);

    expect(await screen.findByText('No backups yet')).toBeInTheDocument();
  });

  it('creates a backup and refreshes the list', async () => {
    const created: Backup = {
      name: 'caldart-20260615-101500.sql.gz',
      size_bytes: 2_500_000,
      created_at: '2026-06-15T10:15:00Z',
    };
    let rows: Backup[] = [];
    server.use(
      http.get(`${API}/system/backups`, () => HttpResponse.json(rows)),
      http.post(`${API}/system/backups`, () => {
        rows = [created];
        return HttpResponse.json(created, { status: 201 });
      }),
    );
    renderWithProviders(<BackupsPanel />);
    await screen.findByText('No backups yet');

    await userEvent.click(screen.getByRole('button', { name: 'Create backup' }));

    expect(await screen.findByText(created.name)).toBeInTheDocument();
    // The toast confirms it, so a slow dump cannot look like a no-op.
    expect(screen.getByText(`Wrote ${created.name}`)).toBeInTheDocument();
  });

  it('shows progress while pg_dump runs', async () => {
    server.use(
      listHandler([]),
      http.post(`${API}/system/backups`, async () => {
        await delay(50);
        return HttpResponse.json(BACKUPS[0], { status: 201 });
      }),
    );
    renderWithProviders(<BackupsPanel />);
    await screen.findByText('No backups yet');

    await userEvent.click(screen.getByRole('button', { name: 'Create backup' }));

    const button = await screen.findByRole('button', { name: 'Taking a backup…' });
    expect(button).toBeDisabled();
    expect(screen.getByText(/pg_dump is running/)).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Create backup' })).toBeEnabled(),
    );
  });

  it('reports a failed backup without losing the list', async () => {
    server.use(
      listHandler(BACKUPS),
      http.post(`${API}/system/backups`, () =>
        HttpResponse.json({ detail: 'pg_dump: could not connect' }, { status: 400 }),
      ),
    );
    renderWithProviders(<BackupsPanel />);
    await screen.findByText(BACKUPS[0]!.name);

    await userEvent.click(screen.getByRole('button', { name: 'Create backup' }));

    expect(await screen.findByText('pg_dump: could not connect')).toBeInTheDocument();
    expect(screen.getByText(BACKUPS[0]!.name)).toBeInTheDocument();
  });

  it('surfaces a listing error', async () => {
    server.use(
      http.get(`${API}/system/backups`, () =>
        HttpResponse.json({ detail: 'Nope' }, { status: 500 }),
      ),
    );
    renderWithProviders(<BackupsPanel />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Nope');
  });
});
