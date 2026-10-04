/**
 * `/email-preferences` — the types of bulk email a signed-in person receives.
 *
 * One switch per type that may be turned off, each saved the moment it moves. Mail
 * about the person's own account (receipts, reminders, password links) is not bulk
 * email and is not listed.
 */
import type { JSX } from 'react';

import { Card } from '@/portal/components/Card';
import { Page } from '@/portal/components/Page';
import { useMyEmailPreferences, useSaveMyEmailPreference } from './api';
import { EmailPreferenceSwitches } from './EmailPreferenceSwitches';

/** The signed-in person's own email preferences. */
export function EmailPreferencesPage(): JSX.Element {
  const preferences = useMyEmailPreferences();
  const save = useSaveMyEmailPreference();

  return (
    <Page
      title="Email preferences"
      lede="CalDART writes to its members and friends about a few different things. Turn off any type of email you would rather not receive; each change is saved at once."
    >
      <Card>
        <EmailPreferenceSwitches
          preferences={preferences}
          save={save}
          label="Types of email you receive"
        />
        <p className="muted">
          Email about your own account, such as receipts, renewal reminders, and password links,
          always reaches you. The unsubscribe link at the foot of a CalDART email turns off that one
          type, and you can turn it back on here.
        </p>
      </Card>
    </Page>
  );
}
