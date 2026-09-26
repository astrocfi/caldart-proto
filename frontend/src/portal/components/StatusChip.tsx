import type { JSX } from 'react';

import type { MembershipStatus, PaymentState } from '../api/types';
import { MEMBERSHIP_STATUS_LABELS, PAYMENT_STATUS_LABELS } from '../choices';

export type StatusTone = 'current' | 'expiring' | 'new' | 'expired' | 'none';

const TONE_CLASS: Record<StatusTone, string> = {
  current: 'chip--ok',
  expiring: 'chip--warn',
  new: 'chip--info',
  expired: 'chip--bad',
  none: 'chip--neutral',
};

// The `current`, `expired` and `none` tones read the same words as the member
// report and the member list's status filter: `none` is the quiet tone of a
// friend, never current and never expired.  `expiring` is a tone of its own,
// with no membership-state code behind it, and `new` is a palette tone other
// features give their own label; no membership takes it.
const TONE_LABEL: Record<StatusTone, string> = {
  current: MEMBERSHIP_STATUS_LABELS.current,
  new: 'Pending',
  expired: MEMBERSHIP_STATUS_LABELS.expired,
  none: MEMBERSHIP_STATUS_LABELS.friend,
  expiring: 'Expiring soon',
};

/** Days before expiry at which a membership counts as "expiring soon". */
export const EXPIRING_WINDOW_DAYS = 30;

/** Days between `today` and `iso`, or null when there is no date. */
export function daysUntil(iso: string | null, today: Date = new Date()): number | null {
  if (!iso) return null;
  const target = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(target.getTime())) return null;
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((target.getTime() - start.getTime()) / 86_400_000);
}

/** Map a membership payload onto one of the chip tones. */
export function membershipTone(
  membership: Pick<MembershipStatus, 'status' | 'expires_on' | 'is_lifetime'>,
  today: Date = new Date(),
): StatusTone {
  if (membership.status === 'friend' || membership.status === 'donor') return 'none';
  if (membership.status === 'expired') return 'expired';
  if (membership.is_lifetime) return 'current';
  const days = daysUntil(membership.expires_on, today);
  if (days !== null && days <= EXPIRING_WINDOW_DAYS) return 'expiring';
  return 'current';
}

export interface StatusChipProps {
  tone: StatusTone;
  label?: string;
  title?: string;
}

/** The base tone-colored chip; most callers want {@link MembershipChip} or a sibling instead. */
export function StatusChip({ tone, label, title }: StatusChipProps): JSX.Element {
  return (
    <span className={`chip ${TONE_CLASS[tone]}`} data-tone={tone} title={title}>
      {label ?? TONE_LABEL[tone]}
    </span>
  );
}

export interface MembershipChipProps {
  membership: Pick<MembershipStatus, 'status' | 'expires_on' | 'is_lifetime' | 'plan'>;
  today?: Date;
}

/** The chip most screens want: tone and wording derived from the membership. */
export function MembershipChip({ membership, today }: MembershipChipProps): JSX.Element {
  const tone = membershipTone(membership, today);
  if (membership.is_lifetime && membership.status === 'current') {
    // "Never expires" rather than "Lifetime member": the screens that show this
    // chip already say the membership is a lifetime one, and the chip's job is
    // to answer the question the other tones answer -- when does it run out.
    return <StatusChip tone="current" label="Never expires" />;
  }
  if (membership.status === 'friend') {
    return <StatusChip tone={tone} label={MEMBERSHIP_STATUS_LABELS.friend} />;
  }
  return <StatusChip tone={tone} title={membership.expires_on ?? undefined} />;
}

export interface StatusDotProps {
  tone: StatusTone;
  /** What the dot means, read out and shown on hover. */
  label: string;
}

/**
 * A tone-colored dot for a dense table, where a chip beside every row would
 * shout. The meaning is carried by the accessible name, never by color alone.
 */
export function StatusDot({ tone, label }: StatusDotProps): JSX.Element {
  return (
    <span className="status-dot" data-tone={tone} title={label}>
      <span className="visually-hidden">{label}</span>
    </span>
  );
}

export interface MembershipDotProps {
  membership: Pick<MembershipStatus, 'status' | 'expires_on' | 'is_lifetime'>;
  today?: Date;
}

/** The membership's tone as a dot: green current, amber expiring, red expired. */
export function MembershipDot({ membership, today }: MembershipDotProps): JSX.Element {
  const tone = membershipTone(membership, today);
  return <StatusDot tone={tone} label={membershipDotLabel(membership, tone)} />;
}

/** What a membership dot is read out as: the chip's own word for the same state. */
function membershipDotLabel(
  membership: Pick<MembershipStatus, 'status' | 'is_lifetime'>,
  tone: StatusTone,
): string {
  if (membership.is_lifetime && membership.status === 'current') return 'Never expires';
  if (membership.status === 'friend') return MEMBERSHIP_STATUS_LABELS.friend;
  return TONE_LABEL[tone];
}

/**
 * Whether this member may fly for CalDART today: a tick when the medical is in
 * date, a cross when it has lapsed, and a dash for somebody who holds none.
 */
export function PilotMark({
  isPilot,
  isCurrent,
}: {
  isPilot: boolean;
  isCurrent: boolean;
}): JSX.Element {
  if (!isPilot) {
    return (
      <span className="pilot-mark" data-state="none" title="Not a pilot">
        <span aria-hidden="true">—</span>
        <span className="visually-hidden">Not a pilot</span>
      </span>
    );
  }
  const label = isCurrent ? 'Medical current' : 'Medical expired';
  return (
    <span className="pilot-mark" data-state={isCurrent ? 'ok' : 'bad'} title={label}>
      <span aria-hidden="true">{isCurrent ? '✓' : '✗'}</span>
      <span className="visually-hidden">{label}</span>
    </span>
  );
}

/** Chip for a plain currency flag, such as insurance or medical currency. */
export function CurrencyChip({
  isCurrent,
  missing = false,
}: {
  isCurrent: boolean;
  missing?: boolean;
}): JSX.Element {
  if (missing) return <StatusChip tone="none" label="Not on file" />;
  return isCurrent ? (
    <StatusChip tone="current" label="Current" />
  ) : (
    <StatusChip tone="expired" label="Expired" />
  );
}

/** A payment's state, in the shared status palette. */
export function paymentStatusTone(status: PaymentState): StatusTone {
  if (status === 'succeeded') return 'current';
  if (status === 'pending') return 'expiring';
  if (status === 'failed') return 'expired';
  return 'none';
}

/** Chip for a payment's state, in the shared status palette. */
export function PaymentChip({ status }: { status: PaymentState }): JSX.Element {
  return <StatusChip tone={paymentStatusTone(status)} label={PAYMENT_STATUS_LABELS[status]} />;
}
