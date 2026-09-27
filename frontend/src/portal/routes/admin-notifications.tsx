/** The notifications screen: which address hears about which event. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const adminNotificationsRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['account_admin']} />,
    children: [
      {
        path: 'admin/notifications',
        lazy: async () => ({
          Component: (await import('../features/admin-notifications/AdminNotificationsPage'))
            .AdminNotificationsPage,
        }),
      },
    ],
  },
];
