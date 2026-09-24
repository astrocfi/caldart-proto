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
  // #reports-renewals — the Reconciliation, Contributions and Renewals tabs.
  // A treasurer reaches the finance area too: it carries money, never the
  // medical and certificate detail on a member record.
  {
    element: <RequireRole roles={['account_admin', 'treasurer']} />,
    children: [
      {
        path: 'admin/payments/reconciliation',
        lazy: async () => ({
          Component: (await import('../features/admin-payments/ReconciliationPage'))
            .ReconciliationPage,
        }),
      },
      {
        path: 'admin/payments/contributions',
        lazy: async () => ({
          Component: (await import('../features/admin-payments/ContributionsPage'))
            .ContributionsPage,
        }),
      },
      {
        path: 'admin/payments/renewals',
        lazy: async () => ({
          Component: (await import('../features/admin-payments/RenewalsPage')).RenewalsPage,
        }),
      },
    ],
  },
];
