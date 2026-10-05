/**
 * Where a person's membership stands, in words, for the member record's summary strip
 * and the user record's Membership card.
 *
 * A member with no term in force is never called a friend: one whose terms a deactivation
 * set aside says so, and one with no term reads that there is none, with where to grant
 * one when the reader can.  Anybody else gets the membership's dot, plan, and expiry.
 */
import type { JSX } from 'react';

import type { AccountKind, IsoDate, MemberTerm, MembershipStatus } from '@/portal/api/types';
import { DateText } from '@/portal/components/DateText';
import { MembershipDot, StatusDot } from '@/portal/components/StatusDot';
import './members.css';

/** What the wording needs to know about the account and its terms. */
export interface MembershipFacts {
  kind: AccountKind;
  isActive: boolean;
  membership: MembershipStatus;
  friendOn: IsoDate | null;
  /** The account holds any term at all. */
  hasTerms: boolean;
  /** A deactivation set one of its terms aside. */
  hasSetAside: boolean;
}

/** The facts the member record's own term list gives. */
export function factsFromTerms(
  {
    kind,
    is_active: isActive,
    membership,
    friend_on: friendOn,
  }: {
    kind: AccountKind;
    is_active: boolean;
    membership: MembershipStatus;
    friend_on: IsoDate | null;
  },
  terms: MemberTerm[],
): MembershipFacts {
  return {
    kind,
    isActive,
    membership,
    friendOn,
    hasTerms: terms.length > 0,
    hasSetAside: terms.some((term) => term.status === 'suspended'),
  };
}

export interface MembershipSummaryProps {
  facts: MembershipFacts;
  /** Say where a term is granted, for a reader who can grant one there. */
  grantHint?: boolean;
}

/** The membership in words: a dot and its state, or a sentence where a dot would mislead. */
export function MembershipSummary({
  facts,
  grantHint = false,
}: MembershipSummaryProps): JSX.Element {
  const isMember = facts.kind === 'member';
  const hasNone = facts.membership.status === 'none';
  if (isMember && !facts.isActive && facts.hasSetAside) {
    return (
      <span className="membership-summary">
        <StatusDot tone="none" label="Membership set aside while deactivated" />
      </span>
    );
  }
  if (hasNone) {
    const none = facts.hasTerms ? 'No membership in force' : 'No membership yet';
    return (
      <span className="membership-summary">
        <StatusDot tone="none" label={grantHint ? `${none}: grant a term on Memberships` : none} />
      </span>
    );
  }
  const { membership } = facts;
  return (
    <>
      <MembershipDot membership={membership} />
      {membership.plan ? <span className="muted">{membership.plan}</span> : null}
      {membership.is_lifetime || membership.expires_on === null ? null : (
        <span className="muted">
          expires <DateText value={membership.expires_on} />
        </span>
      )}
    </>
  );
}
