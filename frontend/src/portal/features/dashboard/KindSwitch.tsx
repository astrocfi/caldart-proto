/**
 * Switching between a member and a friend of CalDART.
 *
 * `KindSwitch` is the control the dashboard's membership card and the profile's
 * **Your kind of account** card share.  A member (not a life member) gets **Make me a
 * friend**, which opens a confirmation panel: their membership stays current to its
 * end and they become a friend the day after, or at once when nothing is current.  When
 * the automatic renewal also takes a contribution, the panel asks whether to keep it as
 * a yearly recurring donation.  A member whose change is pending sees the day and an
 * **Undo** button; a friend gets **Make me a member**, which leads to the checkout.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import { useRenewal } from '@/portal/api/queries';
import type { IsoDate, MembershipStatus, RenewalMandate, User } from '@/portal/api/types';
import { useAuth } from '@/portal/auth/useAuth';
import { Button, ButtonLink } from '@/portal/components/Button';
import { Card } from '@/portal/components/Card';
import { formatDate, todayIso } from '@/portal/components/DateText';
import { formatCents } from '@/portal/components/Money';
import { FormAlert } from '@/portal/features/auth/form';
import { useBecomeFriend, useUndoBecomeFriend } from '@/portal/features/profile/api';

/** Where a friend goes to pay dues and become a member. */
export const JOIN_AS_MEMBER_PATH = '/membership/join';

/** Which of the four things the control can offer applies to the signed-in person. */
export type KindState =
  | { kind: 'friend' }
  | { kind: 'lifetime' }
  | { kind: 'pending'; friendOn: IsoDate }
  /** `expiresOn` is the end of a current membership, or null when none is current. */
  | { kind: 'member'; expiresOn: IsoDate | null };

/**
 * Works out what the kind control offers `user`, whose membership reads `status`.
 *
 * A friend by the membership state (which includes a member who registered and has
 * not yet paid, so they are offered **Make me a member**), a current life member, a
 * member with a pending `friend_on`, and otherwise a member.
 */
export function kindState(user: User, status: MembershipStatus): KindState {
  if (status.status === 'friend') return { kind: 'friend' };
  if (status.is_lifetime && status.status === 'current') return { kind: 'lifetime' };
  if (user.friend_on !== null) return { kind: 'pending', friendOn: user.friend_on };
  return {
    kind: 'member',
    expiresOn: status.status === 'current' ? status.expires_on : null,
  };
}

/** The day after `iso`, as `YYYY-MM-DD`. */
function dayAfter(iso: IsoDate): IsoDate {
  const next = new Date(`${iso}T00:00:00`);
  next.setDate(next.getDate() + 1);
  return todayIso(next);
}

/**
 * What an active automatic renewal gives on top of the dues, in cents; 0 for none.  A
 * paused renewal's contribution is not offered: its card already failed, or its member
 * was told it is off, so switching simply stops it.
 */
function renewalContribution(mandate: RenewalMandate | null | undefined): number {
  if (mandate?.status !== 'active') return 0;
  return mandate.contribution_cents;
}

/**
 * What the control offers the signed-in person, read off the user payload alone: it
 * carries the membership, and every change of kind or payment refreshes it.
 */
function useKindState(): KindState | null {
  const { user } = useAuth();
  return user ? kindState(user, user.membership) : null;
}

/** The button, the confirmation panel, or the pending change, as `kindState` says. */
export function KindSwitch(): JSX.Element | null {
  const state = useKindState();
  if (state === null || state.kind === 'lifetime') return null;
  if (state.kind === 'friend') {
    return (
      <ButtonLink to={JOIN_AS_MEMBER_PATH} variant="secondary">
        Make me a member
      </ButtonLink>
    );
  }
  if (state.kind === 'pending') return <PendingChange friendOn={state.friendOn} />;
  return <BecomeFriend expiresOn={state.expiresOn} />;
}

/** The `Your kind of account` card on the profile page. */
export function KindCard(): JSX.Element | null {
  const state = useKindState();
  if (state === null) return null;
  return (
    <Card title="Your kind of account">
      <div className="stack">
        <p>{KIND_SENTENCES[state.kind]}</p>
        <div className="cluster">
          <KindSwitch />
        </div>
      </div>
    </Card>
  );
}

/** The sentence the profile card opens with for each state. */
const KIND_SENTENCES: Record<KindState['kind'], string> = {
  friend: 'You are a friend of CalDART: no dues, no expiry. Become a member any time.',
  lifetime: 'You are a life member of CalDART.',
  pending: 'You are a member of CalDART.',
  member: 'You are a member of CalDART.',
};

/** A change to friend waiting for its day, with the way to take it back. */
function PendingChange({ friendOn }: { friendOn: IsoDate }) {
  const undo = useUndoBecomeFriend();
  return (
    <div className="cluster">
      <p>You become a friend on {formatDate(friendOn)}.</p>
      <Button variant="secondary" disabled={undo.isPending} onClick={() => undo.mutate()}>
        Undo
      </Button>
      <FormAlert error={undo.error} />
    </div>
  );
}

/** **Make me a friend**, and the confirmation panel it opens. */
function BecomeFriend({ expiresOn }: { expiresOn: IsoDate | null }) {
  const [isOpen, setIsOpen] = useState(false);
  const renewal = useRenewal();
  const become = useBecomeFriend();

  if (!isOpen) {
    return (
      <Button variant="secondary" onClick={() => setIsOpen(true)}>
        Make me a friend
      </Button>
    );
  }

  // Until the renewal has loaded nobody knows whether there is a contribution to ask
  // about, so the confirm buttons wait for it.
  const isBusy = become.isPending || renewal.isPending;
  const contribution = renewalContribution(renewal.data?.mandate);
  const amount = formatCents(contribution, { whole: true });
  const handleConfirm = (keepContribution?: boolean) =>
    become.mutate(keepContribution === undefined ? {} : { keep_contribution: keepContribution });

  return (
    <section className="stack-tight" aria-label="Make me a friend">
      <p>
        {expiresOn === null
          ? 'You become a friend of CalDART today: no dues, no expiry, and no renewal reminders.'
          : `Your membership stays current through ${formatDate(expiresOn)}. ` +
            `On ${formatDate(dayAfter(expiresOn))} you become a friend of CalDART: no dues, ` +
            'no expiry, and no renewal reminders.'}
      </p>
      {contribution > 0 ? (
        <p>
          Your automatic renewal also gives {amount} each year. Keep giving {amount} a year as a
          recurring donation?
        </p>
      ) : null}
      <div className="cluster">
        {contribution > 0 ? (
          <>
            <Button disabled={isBusy} onClick={() => handleConfirm(true)}>
              Keep the contribution
            </Button>
            <Button variant="secondary" disabled={isBusy} onClick={() => handleConfirm(false)}>
              Stop it
            </Button>
          </>
        ) : (
          <Button disabled={isBusy} onClick={() => handleConfirm()}>
            Make me a friend
          </Button>
        )}
        <Button variant="quiet" onClick={() => setIsOpen(false)}>
          Cancel
        </Button>
      </div>
      <FormAlert error={become.error} />
    </section>
  );
}
