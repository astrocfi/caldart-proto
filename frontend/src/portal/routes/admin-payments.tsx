/** Payment reporting routes. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';
import { AdminPaymentsPage } from '../features/admin-payments';

export const adminPaymentsRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['account_admin']} />,
    children: [{ path: 'admin/payments', element: <AdminPaymentsPage /> }],
  },
];
