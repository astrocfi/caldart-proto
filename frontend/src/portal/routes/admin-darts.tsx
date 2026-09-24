/** DART administration routes. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const adminDartsRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['account_admin']} />,
    children: [
      {
        path: 'admin/darts',
        lazy: async () => ({
          Component: (await import('../features/admin-darts/DartsPage')).DartsPage,
        }),
      },
    ],
  },
];
