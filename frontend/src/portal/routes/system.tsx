/** System administration routes. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';
import { SystemPage } from '../features/system';

export const systemRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['system_admin']} />,
    children: [{ path: 'system', element: <SystemPage /> }],
  },
];
