/**
 * `/portal/system` — health, backups, reminders, the email log, the scheduled
 * reports, renewals, the year-end statements, and the FAA registry import.
 */
import type { JSX } from 'react';

import { Page } from '@/portal/components/Page';
import { BackupsPanel } from './BackupsPanel';
import { EmailLogPanel } from './EmailLogPanel';
import { HealthPanel } from './HealthPanel';
import { RegistryPanel } from './RegistryPanel';
import { RemindersPanel } from './RemindersPanel';
import { RenewalsPanel } from './RenewalsPanel';
import { ReportsPanel } from './ReportsPanel';
import { StatementsPanel } from './StatementsPanel';

/**
 * Renders the system administration screen: health, backups, reminders, the
 * email log, the scheduled reports, renewals, the year-end statements, and the
 * FAA registry import.
 */
export function SystemPage(): JSX.Element {
  return (
    <Page
      title="System"
      eyebrow="Administration"
      lede="How the server is doing, the database dumps it holds, and the five jobs it runs on a schedule."
    >
      <HealthPanel />
      <BackupsPanel />
      <RemindersPanel />
      <EmailLogPanel />
      <ReportsPanel />
      <RenewalsPanel />
      <StatementsPanel />
      <RegistryPanel />
    </Page>
  );
}
