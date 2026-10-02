/**
 * `/portal/system/scheduled` — the jobs the server runs on a schedule, each with
 * **Run now** and a dry run.
 *
 * The renewal reminder emails and the automatic renewal charges come first
 * because they are the pair readers confuse: one only emails, the other takes
 * the money, and the charges run before the emails each morning.  The reminder
 * schedule sits beside the reminder emails it dates.
 */
import type { JSX } from 'react';

import { Page } from '@/portal/components/Page';
import { BouncesPanel } from './BouncesPanel';
import { ReminderScheduleCard } from './ReminderScheduleCard';
import { RemindersPanel } from './RemindersPanel';
import { RenewalsPanel } from './RenewalsPanel';
import { ReportsPanel } from './ReportsPanel';
import { StatementsPanel } from './StatementsPanel';

/**
 * Renders the Scheduled page: the renewal reminder emails and their schedule, the
 * automatic renewal charges, the scheduled reports, the year-end statements, and the
 * bounce check, in that order.
 */
export function ScheduledPage(): JSX.Element {
  return (
    <Page
      title="Scheduled"
      eyebrow="System"
      lede="The jobs the server runs on a schedule. Each one can be run by hand here, and a dry run shows what it would do."
    >
      <RemindersPanel />
      <ReminderScheduleCard />
      <RenewalsPanel />
      <ReportsPanel />
      <StatementsPanel />
      <BouncesPanel />
    </Page>
  );
}
