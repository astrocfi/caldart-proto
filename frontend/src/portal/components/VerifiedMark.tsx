import type { JSX } from 'react';

import type { Verification } from '@/portal/api/types';
import { DateText } from './DateText';
import { StatusDot } from './StatusDot';

/** An item's verified state: the full stamp, or only the flag a summary row carries. */
export type VerificationLike = Pick<Verification, 'verified'> &
  Partial<Pick<Verification, 'verified_by' | 'verified_at'>>;

export interface VerifiedMarkProps {
  verification: VerificationLike;
  /** The member's own wording for an unverified item: *Not yet verified*. */
  pending?: boolean;
  /** The item's date has passed: *Expired* comes first, whatever its verification. */
  expired?: boolean;
}

/**
 * Whether an authority has checked an item: *Verified by <name> on <date>*, or *Not
 * verified*, as a dot with its word, amber because a check nobody has made yet is a normal waiting
 * state, not an alarm.  An item whose date has passed reads *Expired* first, in the
 * expired tone, so a lapsed medical never reads as cleared beside a green *Verified*.
 *
 * Shared by the member check, the aircraft check, both records, and the member's own
 * profile and aircraft, so a pilot certificate reads the same wherever it is shown.
 * The name or the date is left out when the stamp does not carry it.  A caller draws no
 * mark at all for an item the person does not hold, since there is nothing to verify.
 */
export function VerifiedMark({
  verification,
  pending = false,
  expired = false,
}: VerifiedMarkProps): JSX.Element {
  const lapsed = expired ? <StatusDot tone="expired" label="Expired" /> : null;
  if (!verification.verified) {
    return (
      <span className="verified-mark">
        {lapsed}
        <StatusDot tone="expiring" label={pending ? 'Not yet verified' : 'Not verified'} />
      </span>
    );
  }
  const by = verification.verified_by ?? null;
  const at = verification.verified_at ?? null;
  return (
    <span className="verified-mark">
      {lapsed}
      <StatusDot tone="current" label="Verified" />
      {by !== null ? ` by ${by}` : null}
      {at !== null ? (
        <>
          {' on '}
          <DateText value={at} />
        </>
      ) : null}
    </span>
  );
}
