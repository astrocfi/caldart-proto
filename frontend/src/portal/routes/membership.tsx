/** Becoming a member from a friend's account. */
import type { RouteObject } from 'react-router-dom';

/** Paying dues needs a session, so this is mounted behind `RequireAuth`. */
export const membershipRoutes: RouteObject[] = [
  {
    path: 'membership/join',
    lazy: async () => ({
      Component: (await import('../features/membership/JoinAsMemberPage')).JoinAsMemberPage,
    }),
  },
];
