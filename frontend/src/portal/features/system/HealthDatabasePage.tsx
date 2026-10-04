/**
 * `/portal/system/health` — how the server is doing, the database dumps it
 * holds, and the FAA aircraft registry it loads.
 */
import type { JSX } from 'react';

import { Page } from '@/portal/components/Page';
import { BackupsPanel } from './BackupsPanel';
import { HealthPanel } from './HealthPanel';
import { RegistryPanel } from './RegistryPanel';

/** Renders the Health and database page: the health checks, backups, and aircraft database. */
export function HealthDatabasePage(): JSX.Element {
  return (
    <Page
      title="Health and database"
      lede="How the server is doing, the backups it holds, and the FAA aircraft data it loads."
    >
      <HealthPanel />
      <BackupsPanel />
      <RegistryPanel />
    </Page>
  );
}
