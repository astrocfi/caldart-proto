/** Payment reporting routes (PLAN §8).  Owned by `feat/payments`. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';
import { comingSoon } from './placeholder';

const BRANCH = 'feat/payments';

export const adminPaymentsRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['account_admin']} />,
    children: [{ path: 'admin/payments', element: comingSoon('Payments and reports', BRANCH) }],
  },
];
