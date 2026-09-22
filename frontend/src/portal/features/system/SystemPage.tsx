/** `/portal/system` — health, backups and reminders. */
import type { JSX } from 'react';

import { Page } from '@/portal/components/Page';
import { BackupsPanel } from './BackupsPanel';
import { HealthPanel } from './HealthPanel';
import { RemindersPanel } from './RemindersPanel';

/** Renders the system administration screen: health, backups and reminders. */
export function SystemPage(): JSX.Element {
  return (
    <Page
      title="System"
      eyebrow="Administration"
      lede="How the server is doing, the database dumps it holds, and the renewal reminders it sends."
    >
      <HealthPanel />
      <BackupsPanel />
      <RemindersPanel />
    </Page>
  );
}
