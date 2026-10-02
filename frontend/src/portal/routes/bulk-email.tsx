/** CalDART management's bulk email route. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const bulkEmailRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['management']} />,
    children: [
      {
        path: 'admin/bulk-email',
        lazy: async () => ({
          Component: (await import('../features/bulk-email/BulkEmailPage')).BulkEmailPage,
        }),
      },
    ],
  },
];
