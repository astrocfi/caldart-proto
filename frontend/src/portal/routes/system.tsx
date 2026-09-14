/** System administration routes. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const systemRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['system_admin']} />,
    children: [
      {
        path: 'system',
        lazy: async () => ({
          Component: (await import('../features/system/SystemPage')).SystemPage,
        }),
      },
    ],
  },
];
