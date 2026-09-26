/** The Donate screen: a gift given once or on a schedule. */
import type { RouteObject } from 'react-router-dom';

export const donateRoutes: RouteObject[] = [
  {
    path: 'donate',
    lazy: async () => ({
      Component: (await import('../features/donate/DonatePage')).DonatePage,
    }),
  },
];
