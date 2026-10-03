/**
 * CalDART management's bulk email screens: Compose, the compose screen of one
 * draft, Drafts & scheduled, Sent, and one send's detail.
 */
import type { RouteObject } from 'react-router-dom';

import { RequireRole } from '../auth/guards';

export const bulkEmailRoutes: RouteObject[] = [
  {
    element: <RequireRole roles={['management']} />,
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
];
