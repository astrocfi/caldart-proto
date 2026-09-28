/**
 * `/portal/system/scheduled` — the jobs the server runs on a schedule, each with
 * **Run now** and a dry run.
 *
 * The renewal reminder emails and the automatic renewal charges come first
 * because they are the pair readers confuse: one only emails, the other takes
 * the money, and the charges run before the emails each morning.
 */
import type { JSX } from 'react';

import { Page } from '@/portal/components/Page';
import { RemindersPanel } from './RemindersPanel';
import { RenewalsPanel } from './RenewalsPanel';
import { ReportsPanel } from './ReportsPanel';
import { StatementsPanel } from './StatementsPanel';

/**
 * Renders the Scheduled page: the renewal reminder emails, the automatic renewal
 * charges, the scheduled reports, and the year-end statements, in that order.
 */
export function ScheduledPage(): JSX.Element {
  return (
    <Page
      title="Scheduled"
      eyebrow="System"
      lede="The jobs the server runs on a schedule. Each one can be run by hand here, and a dry run shows what it would do."
    >
      <RemindersPanel />
      <RenewalsPanel />
      <ReportsPanel />
      <StatementsPanel />
    </Page>
  );
}
