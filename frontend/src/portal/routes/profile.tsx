/** Profile routes. */
import type { RouteObject } from 'react-router-dom';

export const profileRoutes: RouteObject[] = [
  {
    path: 'profile',
    lazy: async () => ({
      Component: (await import('../features/profile/ProfilePage')).ProfilePage,
    }),
  },
  {
    path: 'profile/aircraft',
    lazy: async () => ({
      Component: (await import('../features/profile/MyAircraftPage')).MyAircraftPage,
    }),
  },
];
