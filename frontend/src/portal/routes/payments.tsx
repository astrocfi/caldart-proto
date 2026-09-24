/** The member's own payments, receipts and automatic renewal. */
import type { RouteObject } from 'react-router-dom';

export const paymentsRoutes: RouteObject[] = [
  {
    path: 'payments',
    lazy: async () => ({
      Component: (await import('../features/payments/PaymentsPage')).PaymentsPage,
    }),
  },
];
