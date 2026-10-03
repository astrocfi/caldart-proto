/** Becoming a member from a friend's account, and every person's email preferences. */
import type { RouteObject } from 'react-router-dom';

/** Both need a session, so these are mounted behind `RequireAuth`. */
export const membershipRoutes: RouteObject[] = [
  {
    path: 'membership/join',
    lazy: async () => ({
      Component: (await import('../features/membership/JoinAsMemberPage')).JoinAsMemberPage,
    }),
  },
  {
    path: 'email-preferences',
    lazy: async () => ({
      Component: (await import('../features/email-preferences/EmailPreferencesPage'))
        .EmailPreferencesPage,
    }),
  },
];
