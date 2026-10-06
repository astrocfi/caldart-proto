/**
 * System administration routes: Health and database, Sent emails and one sent email,
 * and Scheduled.
 * `/system` itself opens Health and database, and so does `/bulk-email/mail-delivery`, the
 * address of the mail delivery check before it became a card on that page.
 */
import { Navigate } from 'react-router-dom';
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const systemRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['system_admin']} />,
    children: [
      { path: 'system', element: <Navigate to="/system/health" replace /> },
      { path: 'bulk-email/mail-delivery', element: <Navigate to="/system/health" replace /> },
      {
        path: 'system/health',
        lazy: async () => ({
          Component: (await import('../features/system/HealthDatabasePage')).HealthDatabasePage,
        }),
      },
      {
        path: 'system/emails',
        lazy: async () => ({
          Component: (await import('../features/system/SentEmailsPage')).SentEmailsPage,
        }),
      },
      {
        path: 'system/emails/:id',
        lazy: async () => ({
          Component: (await import('../features/system/SentEmailPage')).SentEmailPage,
        }),
      },
      {
        path: 'system/scheduled',
        lazy: async () => ({
          Component: (await import('../features/system/ScheduledPage')).ScheduledPage,
        }),
      },
    ],
  },
];
