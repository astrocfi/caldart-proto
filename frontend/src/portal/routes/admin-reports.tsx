/** The reports-by-email screen. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const adminReportsRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['account_admin', 'treasurer']} />,
    children: [
      {
        path: 'admin/reports',
        lazy: async () => ({
          Component: (await import('../features/admin-reports/AdminReportsPage')).AdminReportsPage,
        }),
      },
    ],
  },
];
