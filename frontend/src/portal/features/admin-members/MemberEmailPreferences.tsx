/**
 * The member record's **Email preferences** card: the kinds of bulk email this
 * person receives, with the same switches they see on their own screen.
 *
 * A change made here is saved at once and recorded as the administrator's. A donor
 * receives no bulk email and a deleted member's record cannot change, so neither
 * shows the card.
 */
import type { JSX } from 'react';

import type { MemberDetail } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import {
  useMemberEmailPreferences,
  useSaveMemberEmailPreference,
} from '@/portal/features/email-preferences/api';
import { EmailPreferenceSwitches } from '@/portal/features/email-preferences/EmailPreferenceSwitches';

/** True when `member`'s record shows the Email preferences card. */
export function showsEmailPreferences(member: MemberDetail): boolean {
  return member.kind !== 'donor' && !member.is_tombstone;
}

/** The Email preferences card for `member`; see `showsEmailPreferences` for whose. */
export function MemberEmailPreferences({ member }: { member: MemberDetail }): JSX.Element {
  const preferences = useMemberEmailPreferences(member.id);
  const save = useSaveMemberEmailPreference(member.id);

  return (
    <Card title="Email preferences">
      <p className="muted">
        The kinds of bulk email {member.name} receives. A change here is saved at once and recorded
        as yours; they can change it back on their own Email preferences screen.
      </p>
      <EmailPreferenceSwitches
        preferences={preferences}
        save={save}
        label={`Kinds of email ${member.name} receives`}
      />
    </Card>
  );
}
