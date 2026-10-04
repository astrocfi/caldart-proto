/**
 * The Delete or deactivate tab's account actions: **Make a friend**, and **Deactivate account** or
 * **Reactivate account**.
 *
 * Each asks first. Making a friend does what the member's own switch does: a current
 * membership runs to its end and they become a friend the day after, or at once, and
 * their automatic renewal ends; when that renewal also gives a contribution the panel
 * asks whether to keep it as a recurring donation. Deactivating does what the member's
 * own deactivation does, and reactivating what their own reactivation does. Every
 * refusal the server gives is drawn in the card.
 */
import type { JSX } from 'react';

import type { MemberDetail, RenewalMandate } from '@/portal/api/types';
import { Card } from '@/portal/components/Card';
import { ConfirmButton } from '@/portal/components/ConfirmButton';
import type { ConfirmChoice } from '@/portal/components/ConfirmButton';
import { formatDate } from '@/portal/components/DateText';
import { formatCents } from '@/portal/components/Money';
import { useToast } from '@/portal/components/Toast';
import { FormAlert, fieldError } from '@/portal/features/auth/form';
import { useMemberLedger } from '@/portal/features/admin-payments/api';
import { useDeactivateMember, useMakeFriend, useReactivateMember } from './api';

/** The field a switch to friend answers whether to keep a contribution in. */
const KEEP_FIELD = 'keep_contribution';

/**
 * What an active automatic renewal gives on top of the dues, in cents; 0 for none. A
 * recurring donation is not a renewal, and a paused renewal's contribution simply
 * stops, so neither is offered.
 */
function renewalContribution(mandate: RenewalMandate | null | undefined): number {
  if (mandate?.plan === null || mandate?.status !== 'active') return 0;
  return mandate.contribution_cents;
}

/** True when `member` is a member who can still be made a friend. */
function canBecomeFriend(member: MemberDetail): boolean {
  if (member.kind !== 'member' || member.membership.status === 'friend') return false;
  return !(member.membership.is_lifetime && member.membership.status === 'current');
}

/** The Delete or deactivate tab card holding the account actions for `member`. */
export function MemberAccountActions({ member }: { member: MemberDetail }): JSX.Element | null {
  if (member.kind === 'donor') return null;
  return (
    <Card title="Account" eyebrow="Delete or deactivate">
      <div className="stack">
        {canBecomeFriend(member) ? <MakeFriend member={member} /> : null}
        {member.is_active ? (
          <Deactivate key="deactivate" member={member} />
        ) : (
          <Reactivate key="reactivate" member={member} />
        )}
      </div>
    </Card>
  );
}

/** **Make a friend**, and the question about a contribution when there is one. */
function MakeFriend({ member }: { member: MemberDetail }) {
  const toast = useToast();
  const make = useMakeFriend(member.id);
  const ledger = useMemberLedger(member.id);
  const contribution = renewalContribution(ledger.data?.mandate);
  // A request that gave no answer and was refused under the field is the server asking
  // the question itself, so the panel asks it rather than showing the refusal.
  const wasAsked =
    make.variables?.keep_contribution === undefined && fieldError(make.error, KEEP_FIELD) !== null;
  const asks = contribution > 0 || wasAsked;
  const expiresOn = member.membership.status === 'current' ? member.membership.expires_on : null;

  if (member.friend_on !== null) {
    return (
      <p>
        {member.name} becomes a friend of CalDART on {formatDate(member.friend_on)}.
      </p>
    );
  }

  const handleChoose = (keep?: boolean) => () =>
    make
      .mutateAsync(keep === undefined ? {} : { keep_contribution: keep })
      .then((updated) =>
        toast.show(
          updated.kind === 'friend'
            ? `${member.name} is now a friend of CalDART.`
            : `${member.name} becomes a friend when their membership runs out.`,
          'success',
        ),
      );

  const choices: ConfirmChoice[] = asks
    ? [
        { label: 'Keep the contribution', onChoose: handleChoose(true) },
        { label: 'Stop it', variant: 'secondary', onChoose: handleChoose(false) },
      ]
    : [{ label: 'Make a friend', onChoose: handleChoose() }];
  const gives = contribution > 0 ? formatCents(contribution, { whole: true }) : 'a contribution';

  return (
    <div className="stack-tight">
      <ConfirmButton
        label="Make a friend"
        disabled={ledger.isPending}
        choices={choices}
        startOnCancel
      >
        <p>
          {expiresOn === null
            ? `${member.name} becomes a friend of CalDART today: no dues, no expiry, and no ` +
              'renewal reminders.'
            : `${member.name}'s membership stays current through ${formatDate(expiresOn)}; ` +
              'they become a friend of CalDART the day after.'}{' '}
          Their automatic renewal is canceled.
        </p>
        {asks ? (
          <p>
            Their automatic renewal also gives {gives} each year. Keep it as a yearly recurring
            donation?
          </p>
        ) : null}
      </ConfirmButton>
      <FormAlert error={make.error} handled={wasAsked ? [KEEP_FIELD] : []} />
    </div>
  );
}

/** **Deactivate account**, as the member's own deactivation would. */
function Deactivate({ member }: { member: MemberDetail }) {
  const toast = useToast();
  const deactivate = useDeactivateMember(member.id);
  const handleDeactivate = () =>
    deactivate
      .mutateAsync()
      .then(() => toast.show(`${member.name}'s account is deactivated.`, 'success'));

  return (
    <div className="stack-tight">
      <ConfirmButton
        label="Deactivate account"
        variant="danger"
        choices={[{ label: 'Deactivate account', variant: 'danger', onChoose: handleDeactivate }]}
      >
        <p>
          {member.name} will be signed out everywhere and cannot sign in until the account is
          reactivated. Their automatic renewal and any recurring donation are canceled, and a
          membership with time left is set aside until they come back. Nothing is deleted.
        </p>
      </ConfirmButton>
      <FormAlert error={deactivate.error} />
    </div>
  );
}

/** **Reactivate account**, as the member's own reactivation would. */
function Reactivate({ member }: { member: MemberDetail }) {
  const toast = useToast();
  const reactivate = useReactivateMember(member.id);
  const handleReactivate = () =>
    reactivate
      .mutateAsync()
      .then(() => toast.show(`${member.name}'s account is active again.`, 'success'));

  return (
    <div className="stack-tight">
      <p>
        {member.reactivation_blocked
          ? 'This account is deactivated, and a user administrator has blocked it from ' +
            'reactivating.'
          : 'This account is deactivated.'}
      </p>
      <ConfirmButton
        label="Reactivate account"
        choices={[{ label: 'Reactivate account', onChoose: handleReactivate }]}
      >
        <p>
          {member.name} can sign in again, and a membership set aside when the account was
          deactivated resumes if it has time left. Automatic renewal stays off.
        </p>
      </ConfirmButton>
      <FormAlert error={reactivate.error} />
    </div>
  );
}
