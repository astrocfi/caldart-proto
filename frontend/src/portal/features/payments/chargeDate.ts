/**
 * The day a standing authority charges on, as the renewal screens handle it.
 *
 * A date box speaks `YYYY-MM-DD` and so does the API, so every date here is that
 * string: comparing two of them lexicographically compares the days themselves.
 *
 * The earliest day a box offers is read from the reader's own clock, while the
 * server judges "already gone by" in the deployment's time zone.  A reader whose
 * day is behind the server's can therefore be offered a day the server refuses;
 * the refusal names the field and carries `The next charge cannot be in the
 * past.`, which both screens show, so the member is told rather than left
 * guessing.
 */
import type { IsoDate } from '@/portal/api/types';
import { todayIso } from '@/portal/components/DateText';

/**
 * The given day, or today when it is null or has already gone by.
 *
 * The renewal setup opens on the day the membership runs out, and on today for a
 * member whose term has gone by or who has none.  A change form opens on the day
 * its authority carries, and that day can be in the past: it is the day of the
 * attempt already scheduled, which waits for the next scan rather than for the
 * calendar.  The box refuses a day before today, so the form opens on today and
 * the member can still change everything else it holds.
 */
export function notBeforeToday(day: IsoDate | null, today: Date = new Date()): IsoDate {
  const earliest = todayIso(today);
  if (day === null || day < earliest) return earliest;
  return day;
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
