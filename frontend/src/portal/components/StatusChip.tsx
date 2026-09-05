import type { MembershipStatus, PaymentState } from '../api/types';
import { PAYMENT_STATUS_LABELS } from '../choices';

export type StatusTone = 'current' | 'expiring' | 'expired' | 'none';

const TONE_CLASS: Record<StatusTone, string> = {
  current: 'chip--ok',
  expiring: 'chip--warn',
  expired: 'chip--bad',
  none: 'chip--neutral',
};

const TONE_LABEL: Record<StatusTone, string> = {
  current: 'Current',
  expiring: 'Expiring soon',
  expired: 'Expired',
  none: 'No membership',
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

/** Map a membership payload onto one of the four chip tones. */
export function membershipTone(
  membership: Pick<MembershipStatus, 'status' | 'expires_on' | 'is_lifetime'>,
  today: Date = new Date(),
): StatusTone {
  if (membership.status === 'none') return 'none';
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

export function StatusChip({ tone, label, title }: StatusChipProps) {
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
export function MembershipChip({ membership, today }: MembershipChipProps) {
  const tone = membershipTone(membership, today);
  if (membership.is_lifetime && membership.status === 'current') {
    return <StatusChip tone="current" label="Lifetime member" />;
  }
  return <StatusChip tone={tone} title={membership.expires_on ?? undefined} />;
}

/** Insurance / medical currency, which is a plain boolean. */
export function CurrencyChip({
  isCurrent,
  missing = false,
}: {
  isCurrent: boolean;
  missing?: boolean;
}) {
  if (missing) return <StatusChip tone="none" label="Not on file" />;
  return isCurrent ? (
    <StatusChip tone="current" label="Current" />
  ) : (
    <StatusChip tone="expired" label="Expired" />
  );
}

/** A payment's state, in the shared status palette (PLAN §4.4). */
export function paymentStatusTone(status: PaymentState): StatusTone {
  if (status === 'succeeded') return 'current';
  if (status === 'pending') return 'expiring';
  if (status === 'failed') return 'expired';
  return 'none';
}

export function PaymentChip({ status }: { status: PaymentState }) {
  return <StatusChip tone={paymentStatusTone(status)} label={PAYMENT_STATUS_LABELS[status]} />;
}
