/**
 * The bulk email screens: Compose, the compose screen of one draft, Drafts &
 * scheduled, Sent, one send's detail, and the Callouts with one callout's answers,
 * for CalDART management and DART leaders; management's Templates, Recipient groups
 * and one group, and Mail delivery; and the system administrator's Email types.
 */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const bulkEmailRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['management', 'dart_leader']} />,
    children: [
      {
        path: 'bulk-email/compose',
        lazy: async () => ({
          Component: (await import('../features/bulk-email/ComposeStart')).ComposeStart,
        }),
      },
      {
        path: 'bulk-email/drafts',
        lazy: async () => ({
          Component: (await import('../features/bulk-email/DraftsPage')).DraftsPage,
        }),
      },
      {
        path: 'bulk-email/compose/:id',
        lazy: async () => ({
          Component: (await import('../features/bulk-email/ComposePage')).ComposePage,
        }),
      },
      {
        path: 'bulk-email/sent',
        lazy: async () => ({
          Component: (await import('../features/bulk-email/SentPage')).SentPage,
        }),
      },
      {
        path: 'bulk-email/sent/:id',
        lazy: async () => ({
          Component: (await import('../features/bulk-email/SentDetailPage')).SentDetailPage,
        }),
      },
      {
        path: 'bulk-email/callouts',
        lazy: async () => ({
          Component: (await import('../features/callouts/CalloutsPage')).CalloutsPage,
        }),
      },
      {
        path: 'bulk-email/callouts/:id',
        lazy: async () => ({
          Component: (await import('../features/callouts/CalloutDetailPage')).CalloutDetailPage,
        }),
      },
    ],
  },
  {
    element: <RequireRole roles={['management']} />,
    children: [
      {
        path: 'bulk-email/templates',
        lazy: async () => ({
          Component: (await import('../features/bulk-email/TemplatesPage')).TemplatesPage,
        }),
      },
      {
        path: 'bulk-email/groups',
        lazy: async () => ({
          Component: (await import('../features/bulk-email/GroupsPage')).GroupsPage,
        }),
      },
      {
        path: 'bulk-email/groups/:id',
        lazy: async () => ({
          Component: (await import('../features/bulk-email/GroupDetailPage')).GroupDetailPage,
        }),
      },
    ],
  },
  {
    element: <RequireRole roles={['management']} />,
    children: [
      {
        path: 'bulk-email/mail-delivery',
        lazy: async () => ({
          Component: (await import('../features/mail-delivery/MailDeliveryPage')).MailDeliveryPage,
        }),
      },
    ],
  },
  {
    element: <RequireRole roles={['system_admin']} />,
    children: [
      {
        path: 'bulk-email/types',
        lazy: async () => ({
          Component: (await import('../features/email-types/EmailTypesPage')).EmailTypesPage,
        }),
      },
    ],
  },
];
