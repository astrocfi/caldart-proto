/**
 * The portal's one way of showing a status: a colored dot followed by its word.
 *
 * The word always carries the meaning, so nothing is said by color alone, and it is
 * set in the normal text color, so it reads on a plain row and a striped one alike.
 * The dot's color is the tone: green current, amber expiring or pending, red expired
 * or failed, blue for something new, and gray for a quiet state.
 */
import type { JSX } from 'react';

import type { MembershipStatus, PaymentState } from '../api/types';
import { MEMBERSHIP_STATUS_LABELS, PAYMENT_STATUS_LABELS } from '../choices';
import { formatDate } from './DateText';

export type StatusTone = 'current' | 'expiring' | 'new' | 'expired' | 'none';

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

/** Map a membership payload onto one of the status tones. */
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

export interface StatusDotProps {
  tone: StatusTone;
  /** The state in words, shown after the dot; the tone's own word when left out. */
  label?: string;
  /** Shown on hover, such as the date a state runs to. */
  title?: string;
  /**
   * Hide the word from sight, keeping it for a screen reader and on hover: only where
   * the value right beside the dot already says it, such as an expiry date in a
   * dense table.
   */
  hideWord?: boolean;
}

/** A status: a tone-colored dot, then its word in the normal text color. */
export function StatusDot({ tone, label, title, hideWord = false }: StatusDotProps): JSX.Element {
  const word = label ?? TONE_LABEL[tone];
  return (
    <span className="status" data-tone={tone} title={title ?? (hideWord ? word : undefined)}>
      <span className="status-dot" data-tone={tone} aria-hidden="true" />
      {hideWord ? <span className="visually-hidden">{word}</span> : word}
    </span>
  );
}

export interface MembershipDotProps {
  membership: Pick<MembershipStatus, 'status' | 'expires_on' | 'is_lifetime'>;
  today?: Date;
  /** Hide the word where the expiry date beside the dot already says it. */
  hideWord?: boolean;
}

/**
 * The membership's state: green current, amber expiring, red expired, gray for a
 * friend, and "Never expires" for a lifetime member.  The date it runs to shows on
 * hover, or, with `hideWord`, the word does.
 */
export function MembershipDot({ membership, today, hideWord }: MembershipDotProps): JSX.Element {
  const tone = membershipTone(membership, today);
  return (
    <StatusDot
      tone={tone}
      label={membershipLabel(membership, tone)}
      title={
        !hideWord && membership.expires_on
          ? `Runs to ${formatDate(membership.expires_on)}`
          : undefined
      }
      hideWord={hideWord}
    />
  );
}

/** The word for a membership's state. */
function membershipLabel(
  membership: Pick<MembershipStatus, 'status' | 'is_lifetime'>,
  tone: StatusTone,
): string {
  // "Never expires" rather than "Lifetime member": the screens that show it already
  // say the membership is a lifetime one, and the word's job is to answer the
  // question the other states answer -- when does it run out.
  if (membership.is_lifetime && membership.status === 'current') return 'Never expires';
  if (membership.status === 'friend') return MEMBERSHIP_STATUS_LABELS.friend;
  if (membership.status === 'donor') return MEMBERSHIP_STATUS_LABELS.donor;
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

/** A plain currency flag, such as insurance or medical currency: Current, Expired, or Not on file. */
export function CurrencyDot({
  isCurrent,
  missing = false,
}: {
  isCurrent: boolean;
  missing?: boolean;
}): JSX.Element {
  if (missing) return <StatusDot tone="none" label="Not on file" />;
  return isCurrent ? (
    <StatusDot tone="current" label="Current" />
  ) : (
    <StatusDot tone="expired" label="Expired" />
  );
}

/** A payment's state, in the shared status palette. */
export function paymentStatusTone(status: PaymentState): StatusTone {
  if (status === 'succeeded') return 'current';
  if (status === 'pending') return 'expiring';
  if (status === 'failed') return 'expired';
  return 'none';
}

/** A payment's state as a dot and its word. */
export function PaymentDot({ status }: { status: PaymentState }): JSX.Element {
  return <StatusDot tone={paymentStatusTone(status)} label={PAYMENT_STATUS_LABELS[status]} />;
}
