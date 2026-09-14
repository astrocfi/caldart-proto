/** Aircraft administration routes. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const adminAircraftRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['account_admin']} />,
    children: [
      {
        path: 'admin/aircraft',
        lazy: async () => ({
          Component: (await import('../features/admin-aircraft/AircraftRegisterPage'))
            .AircraftRegisterPage,
        }),
      },
      {
        path: 'admin/aircraft/:id',
        lazy: async () => ({
          Component: (await import('../features/admin-aircraft/AircraftRecordPage'))
            .AircraftRecordPage,
        }),
      },
    ],
  },
];
