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
        'How the server is doing, the backups it holds, and the FAA aircraft data it loads.',
      ),
    ).toBeInTheDocument();
  });

  it('shows Health, Backups, and FAA aircraft data, in that order', async () => {
    renderWithProviders(<HealthDatabasePage />);

    await screen.findByText('0.1.0');
    const titles = screen
      .getAllByRole('heading', { level: 2 })
      .map((heading) => heading.textContent);
    expect(titles).toEqual(['Health', 'Backups', 'FAA aircraft data']);
  });

  it('says what the FAA aircraft data is and when it loads', async () => {
    renderWithProviders(<HealthDatabasePage />);

    expect(
      await screen.findByText(
        'Loads the FAA aircraft data, which is what the N-number box on an aircraft form ' +
          'offers. It runs every night and changes nothing else.',
      ),
    ).toBeInTheDocument();
  });

  it('renders live data in its panels', async () => {
    renderWithProviders(<HealthDatabasePage />);

    expect(await screen.findByText('0.1.0')).toBeInTheDocument();
    expect(await screen.findByText('No backups yet')).toBeInTheDocument();
  });
});
