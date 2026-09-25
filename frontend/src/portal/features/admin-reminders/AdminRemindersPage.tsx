/**
 * `/admin/reminders` — the account administrator's view of the renewal
 * reminders that have gone out.
 *
 * Read-only: the same log table and kind filter the system administrator's
 * panel shows, without the controls that start a scan.
 */
import type { JSX } from 'react';

import { Card } from '@/portal/components/Card';
import { Page } from '@/portal/components/Page';
import { ReminderLog } from '@/portal/features/system/ReminderLog';

/** Renders the reminder log for an account administrator. */
export function AdminRemindersPage(): JSX.Element {
  return (
    <Page
      title="Reminders"
      eyebrow="Administration"
      lede="The renewal emails CalDART has sent, newest first."
    >
      <Card eyebrow="Membership" title="Renewal reminders">
        <p className="muted">
          The scan runs every morning at 07:00 and mails a member 60, 30, and 7 days before their
          membership ends, on the day it ends, and 30 days after. Each member gets one email per
          membership per kind. This is the record of what renewal emails were sent to each member.
        </p>

        <ReminderLog />
      </Card>
    </Page>
  );
}
