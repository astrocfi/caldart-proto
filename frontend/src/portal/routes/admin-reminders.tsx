/** Renewal reminder log routes. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const adminRemindersRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['account_admin']} />,
    children: [
      {
        path: 'admin/reminders',
        lazy: async () => ({
          Component: (await import('../features/admin-reminders/AdminRemindersPage'))
            .AdminRemindersPage,
        }),
      },
    ],
  },
];
