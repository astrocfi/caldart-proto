/** `/portal/system` — health, backups, reminders, the email log, and renewals. */
import type { JSX } from 'react';

import { Page } from '@/portal/components/Page';
import { BackupsPanel } from './BackupsPanel';
import { EmailLogPanel } from './EmailLogPanel';
import { HealthPanel } from './HealthPanel';
import { RemindersPanel } from './RemindersPanel';
import { RenewalsPanel } from './RenewalsPanel';

/**
 * Renders the system administration screen: health, backups, reminders, the
 * email log, and renewals.
 */
export function SystemPage(): JSX.Element {
  return (
    <Page
      title="System"
      eyebrow="Administration"
      lede="How the server is doing, the database dumps it holds, and the two scans it runs each morning."
    >
      <HealthPanel />
      <BackupsPanel />
      <RemindersPanel />
      <EmailLogPanel />
      <RenewalsPanel />
    </Page>
  );
}
