/**
 * `/admin/notifications` — the account administrator's screen for who hears
 * about what: each email address and the events it is sent a notification of.
 */
import type { JSX } from 'react';

import { Page } from '@/portal/components/Page';
import { NotificationSubscriptionsCard } from './NotificationSubscriptionsCard';

/** Renders the notifications screen. */
export function AdminNotificationsPage(): JSX.Element {
  return (
    <Page title="Notifications" lede="Email addresses that receive notification of system changes">
      <NotificationSubscriptionsCard />
    </Page>
  );
}
