import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { notificationHandlers } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { AdminNotificationsPage } from './AdminNotificationsPage';

describe('AdminNotificationsPage', () => {
  it('is titled Notifications', () => {
    server.use(...notificationHandlers());
    renderWithProviders(<AdminNotificationsPage />);

    expect(screen.getByRole('heading', { level: 1, name: 'Notifications' })).toBeInTheDocument();
  });

  it('holds the subscriptions card', async () => {
    server.use(...notificationHandlers());
    renderWithProviders(<AdminNotificationsPage />);

    expect(
      await screen.findByRole('heading', { name: 'Who hears about what' }),
    ).toBeInTheDocument();
  });
});
