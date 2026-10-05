/**
 * `/admin/reminders` — the account administrator's view of the renewal
 * reminders that have gone out.
 *
 * Read-only: the same log table and kind filter the system administrator's
 * panel shows, without the controls that start a scan, and the reminder schedule
 * without the form that changes it.  The sentence that says when reminders go is
 * built from the saved schedule, so it never disagrees with the schedule card.
 */
import type { JSX } from 'react';

import { Card } from '@/portal/components/Card';
import { Page } from '@/portal/components/Page';
import { useReminderSchedule } from '@/portal/features/system/api';
import { ReminderLog } from '@/portal/features/system/ReminderLog';
import { ReminderScheduleCard } from '@/portal/features/system/ReminderScheduleCard';
import { schedulePhrase } from '@/portal/features/system/reminderSchedule';

/** Renders the reminder log and schedule for an account administrator. */
export function AdminRemindersPage(): JSX.Element {
  const schedule = useReminderSchedule();
  const when =
    schedule.data === undefined
      ? ''
      : `: ${schedulePhrase(schedule.data, {
          before: 'before it ends',
          onTheDay: 'on the day it ends',
        })}`;

  return (
    <Page title="Reminders" lede="The renewal emails CalDART has sent, newest first.">
      <Card title="Renewal reminders">
        <div className="stack">
          <p className="muted">
            Every morning at 7:00 AM, CalDART emails members whose membership is ending{when}.
            Nobody gets the same reminder twice for one membership.
          </p>

          <ReminderLog />
        </div>
      </Card>
      <ReminderScheduleCard readOnly />
    </Page>
  );
}
