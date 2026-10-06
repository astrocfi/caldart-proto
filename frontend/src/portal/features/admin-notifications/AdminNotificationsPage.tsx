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
    <Page
      title="Notification emails"
      lede="Who is emailed when something happens, such as a sign-up, a payment, or a refund."
    >
      <NotificationSubscriptionsCard />
    </Page>
  );
}
