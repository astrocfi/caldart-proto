/** `/portal/system/emails` — the log of every email the site has tried to send. */
import type { JSX } from 'react';

import { Page } from '@/portal/components/Page';
import { EmailLogPanel } from './EmailLogPanel';

/** Renders the Sent emails page, whose body is the email log. */
export function SentEmailsPage(): JSX.Element {
  return (
    <Page title="Sent emails" lede="Every message the site has sent, with who it went to and why.">
      <EmailLogPanel />
    </Page>
  );
}
