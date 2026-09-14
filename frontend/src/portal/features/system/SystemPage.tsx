/** `/portal/system` — health, backups and reminders. */
import { Page } from '../../components/Page';
import { BackupsPanel } from './BackupsPanel';
import { HealthPanel } from './HealthPanel';
import { RemindersPanel } from './RemindersPanel';

export function SystemPage() {
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
