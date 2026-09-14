/** Payment reporting routes. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const adminPaymentsRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['account_admin']} />,
    children: [
      {
        path: 'admin/payments',
        lazy: async () => ({
          Component: (await import('../features/admin-payments/AdminPaymentsPage'))
            .AdminPaymentsPage,
        }),
      },
    ],
  },
];
