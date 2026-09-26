/** The finance area's routes: the overview, the list, the reports, the writes and the ledger. */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

// A treasurer reaches the finance area too: it carries money, never the
// medical and certificate detail on a member record.
export const adminPaymentsRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['account_admin', 'treasurer']} />,
    children: [
      {
        path: 'admin/payments',
        lazy: async () => ({
          Component: (await import('../features/admin-payments/AdminPaymentsPage'))
            .AdminPaymentsPage,
        }),
      },
      {
        path: 'admin/payments/list',
        lazy: async () => ({
          Component: (await import('../features/admin-payments/PaymentsListPage')).PaymentsListPage,
        }),
      },
      {
        path: 'admin/payments/renewals',
        lazy: async () => ({
          Component: (await import('../features/admin-payments/RenewalsPage')).RenewalsPage,
        }),
      },
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
        path: 'admin/payments/record',
        lazy: async () => ({
          Component: (await import('../features/admin-payments/RecordPaymentPage'))
            .RecordPaymentPage,
        }),
      },
      {
        path: 'admin/payments/members/:userId',
        lazy: async () => ({
          Component: (await import('../features/admin-payments/MemberLedgerPage')).MemberLedgerPage,
        }),
      },
      {
        path: 'admin/payments/:id',
        lazy: async () => ({
          Component: (await import('../features/admin-payments/PaymentDetailPage'))
            .PaymentDetailPage,
        }),
      },
    ],
  },
  {
    // The treasurer's own: an account administrator does not reach it.
    element: <RequireRole roles={['treasurer']} />,
    children: [
      {
        path: 'admin/payments/donors',
        lazy: async () => ({
          Component: (await import('../features/admin-payments/DonorsPage')).DonorsPage,
        }),
      },
    ],
  },
];
