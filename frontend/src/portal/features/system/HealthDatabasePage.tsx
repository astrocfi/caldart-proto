/**
 * `/portal/system/health` — how the server is doing, whether other mail systems
 * will trust its email, the database dumps it holds, and the FAA aircraft registry
 * it loads.
 */
import type { JSX } from 'react';

import { Page } from '@/portal/components/Page';
import { BackupsPanel } from './BackupsPanel';
import { HealthPanel } from './HealthPanel';
import { MailDeliveryPanel } from './MailDeliveryPanel';
import { RegistryPanel } from './RegistryPanel';

/** Renders the Health and database page: health, mail delivery, backups, and aircraft data. */
export function HealthDatabasePage(): JSX.Element {
  return (
    <Page
      title="Health and database"
      lede="How the server is doing, whether its email will be trusted, the backups it holds, and the FAA aircraft data it loads."
    >
      <HealthPanel />
      <MailDeliveryPanel />
      <BackupsPanel />
      <RegistryPanel />
    </Page>
  );
}
