/**
 * `/admin/reports` — the reports CalDART emails: the subscriptions an account
 * administrator or a treasurer sets up, and, for an account administrator, the
 * DART rosters that go out each month.
 */
import type { JSX } from 'react';

import { useAuth } from '@/portal/auth/useAuth';
import { Page } from '@/portal/components/Page';
import { hasAnyRole } from '@/portal/nav';
import { RostersCard } from './RostersCard';
import { SubscriptionsCard } from './SubscriptionsCard';

/**
 * Renders the reports screen.
 *
 * Every caller sees the subscriptions for the reports they may read.  The DART
 * rosters are the account administrator's alone, so a treasurer is not shown
 * the card whose endpoints would refuse them.
 */
export function AdminReportsPage(): JSX.Element {
  const { roles } = useAuth();
  const isAccountAdmin = hasAnyRole(roles, ['account_admin']);

  return (
    <Page
      title="Reports"
      eyebrow="Administration"
      lede="The reports CalDART emails on a schedule, and who receives them."
    >
      <SubscriptionsCard />
      {isAccountAdmin ? <RostersCard /> : null}
    </Page>
  );
}
