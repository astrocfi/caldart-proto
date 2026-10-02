/**
 * `/admin/reminders` — the account administrator's view of the renewal
 * reminders that have gone out.
 *
 * Read-only: the same log table and kind filter the system administrator's
 * panel shows, without the controls that start a scan, and the reminder schedule
 * without the form that changes it.
 */
import type { JSX } from 'react';

import { Card } from '@/portal/components/Card';
import { Page } from '@/portal/components/Page';
import { useReminderSchedule } from '@/portal/features/system/api';
import { ReminderLog } from '@/portal/features/system/ReminderLog';
import { ReminderScheduleCard } from '@/portal/features/system/ReminderScheduleCard';
import { days } from '@/portal/features/system/reminderSchedule';

/** Renders the reminder log and schedule for an account administrator. */
export function AdminRemindersPage(): JSX.Element {
  const schedule = useReminderSchedule();
  const when =
    schedule.data === undefined
      ? 'as their membership runs out'
      : `${schedule.data.first_days_before}, ${schedule.data.second_days_before}, and ` +
        `${days(schedule.data.final_days_before)} before their membership ends, on the day ` +
        `it ends, and ${days(schedule.data.lapsed_days_after)} after`;

  return (
    <Page
      title="Reminders"
      eyebrow="Administration"
      lede="The renewal emails CalDART has sent, newest first."
    >
      <Card eyebrow="Membership" title="Renewal reminders">
        <p className="muted">
          The scan runs every morning at 07:00 and mails a member {when}. Each member gets one email
          per membership per kind. This is the record of what renewal emails were sent to each
          member.
        </p>

        <ReminderLog />
      </Card>
      <ReminderScheduleCard readOnly />
    </Page>
  );
}
