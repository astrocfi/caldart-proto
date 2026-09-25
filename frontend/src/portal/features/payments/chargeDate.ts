/**
 * The day a standing authority charges on, as the renewal screens handle it.
 *
 * A date box speaks `YYYY-MM-DD` in the reader's own time zone, and the API
 * takes the same, so every date here is that string: comparing two of them
 * lexicographically compares the days themselves.
 */
import type { IsoDate } from '@/portal/api/types';

/** Today as `YYYY-MM-DD` in the reader's own time zone, for a date box. */
export function todayIso(today: Date = new Date()): IsoDate {
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  return `${today.getFullYear()}-${month}-${day}`;
}

export interface ChargeDateDefault {
  /** True for a life member: their membership has no expiry to charge on. */
  isLifetime: boolean;
  /** The day the membership runs out, or null when it never does or there is none. */
  expiresOn: IsoDate | null;
}

/**
 * The day the setup flow opens on: the day the membership runs out.
 *
 * A life member has no expiry, so theirs falls one year from today instead.  A
 * member whose term has already gone by, or who has none at all, opens on today:
 * the server refuses a day that has already passed, so the box never offers one.
 */
export function defaultChargeDate(
  { isLifetime, expiresOn }: ChargeDateDefault,
  today: Date = new Date(),
): IsoDate {
  const earliest = todayIso(today);
  if (isLifetime) {
    return todayIso(new Date(today.getFullYear() + 1, today.getMonth(), today.getDate()));
  }
  if (expiresOn === null || expiresOn < earliest) return earliest;
  return expiresOn;
}

/**
 * True when a charge falls after the membership it renews has run out.
 *
 * The expiry day itself is still covered, so a charge on it is not late.  A
 * membership that never runs out, and a mandate with no charge waiting, are
 * never late either.
 */
export function isAfterExpiry(chargeOn: IsoDate | null, expiresOn: IsoDate | null): boolean {
  if (chargeOn === null || expiresOn === null) return false;
  return chargeOn > expiresOn;
}
