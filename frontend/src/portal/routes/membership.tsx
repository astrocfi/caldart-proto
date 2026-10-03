/**
 * Becoming a member from a friend's account, and every person's own bulk email: the
 * messages they received and their email preferences.
 */
import type { RouteObject } from 'react-router-dom';

/** Each needs a session, so these are mounted behind `RequireAuth`. */
export const membershipRoutes: RouteObject[] = [
  {
    path: 'membership/join',
    lazy: async () => ({
      Component: (await import('../features/membership/JoinAsMemberPage')).JoinAsMemberPage,
    }),
  },
  {
    path: 'messages',
    lazy: async () => ({
      Component: (await import('../features/messages/MessagesPage')).MessagesPage,
    }),
  },
  {
    path: 'messages/:id',
    lazy: async () => ({
      Component: (await import('../features/messages/MessagePage')).MessagePage,
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
