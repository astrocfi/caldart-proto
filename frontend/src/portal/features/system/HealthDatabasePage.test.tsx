import { screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { HealthDatabasePage } from './HealthDatabasePage';
import { systemPageHandlers } from './pageHandlers';

describe('HealthDatabasePage', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-06-15T12:00:00Z'));
    server.use(...systemPageHandlers());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('is headed Health and database, with its lede', async () => {
    renderWithProviders(<HealthDatabasePage />);

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Health and database' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'How the server is doing, the database dumps it holds, and the aircraft database it loads.',
      ),
    ).toBeInTheDocument();
  });

  it('shows Health, Backups, and Aircraft database, in that order', async () => {
    renderWithProviders(<HealthDatabasePage />);

    await screen.findByText('0.1.0');
    const titles = screen
      .getAllByRole('heading', { level: 2 })
      .map((heading) => heading.textContent);
    expect(titles).toEqual(['Health', 'Backups', 'Aircraft database']);
  });

  it('says what the aircraft database is and that running it again is harmless', async () => {
    renderWithProviders(<HealthDatabasePage />);

    expect(
      await screen.findByText(
        'Loads the FAA aircraft registry, which is what the N-number box on an aircraft form ' +
          'offers. It runs every night and changes nothing else, so running it again is harmless.',
      ),
    ).toBeInTheDocument();
  });

  it('renders live data in its panels', async () => {
    renderWithProviders(<HealthDatabasePage />);

    expect(await screen.findByText('0.1.0')).toBeInTheDocument();
    expect(await screen.findByText('No backups yet')).toBeInTheDocument();
  });
});
