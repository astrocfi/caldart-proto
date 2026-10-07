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

    expect(
      screen.getByRole('heading', { level: 1, name: 'Notification emails' }),
    ).toBeInTheDocument();
  });

  it('holds the subscriptions card', async () => {
    server.use(...notificationHandlers());
    renderWithProviders(<AdminNotificationsPage />);

    expect(
      await screen.findByRole('heading', { level: 2, name: 'Notification emails' }),
    ).toBeInTheDocument();
  });

  it('ledes with what the screen is for', () => {
    server.use(...notificationHandlers());
    renderWithProviders(<AdminNotificationsPage />);

    expect(
      screen.getByText(
        'Who is emailed when something happens, such as a sign-up, a payment, or a refund.',
      ),
    ).toBeInTheDocument();
  });
});
