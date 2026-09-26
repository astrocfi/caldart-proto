/**
 * `/portal/system` — health, backups, reminders, the email log, the scheduled
 * reports, and renewals.
 */
import type { JSX } from 'react';

import { Page } from '@/portal/components/Page';
import { BackupsPanel } from './BackupsPanel';
import { EmailLogPanel } from './EmailLogPanel';
import { HealthPanel } from './HealthPanel';
import { RemindersPanel } from './RemindersPanel';
import { RenewalsPanel } from './RenewalsPanel';
import { ReportsPanel } from './ReportsPanel';
import { StatementsPanel } from './StatementsPanel';

/**
 * Renders the system administration screen: health, backups, reminders, the
 * email log, the scheduled reports, renewals, and the year-end statements.
 */
export function SystemPage(): JSX.Element {
  return (
    <Page
      title="System"
      eyebrow="Administration"
      lede="How the server is doing, the database dumps it holds, and the four jobs it runs on a schedule."
    >
      <HealthPanel />
      <BackupsPanel />
      <RemindersPanel />
      <EmailLogPanel />
      <ReportsPanel />
      <RenewalsPanel />
      <StatementsPanel />
    </Page>
  );
}
