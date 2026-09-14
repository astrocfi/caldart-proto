/** Aircraft administration routes. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';
import { AircraftRecordPage } from '../features/admin-aircraft/AircraftRecordPage';
import { AircraftRegisterPage } from '../features/admin-aircraft/AircraftRegisterPage';

export const adminAircraftRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['account_admin']} />,
    children: [
      { path: 'admin/aircraft', element: <AircraftRegisterPage /> },
      { path: 'admin/aircraft/:id', element: <AircraftRecordPage /> },
    ],
  },
];
