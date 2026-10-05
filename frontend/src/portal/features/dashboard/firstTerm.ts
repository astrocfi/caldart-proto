/**
 * When a member with no membership yet has one coming: the first day of their earliest
 * term still to start.
 */
import type { IsoDate, MembershipTerm } from '@/portal/api/types';
import { todayIso } from '@/portal/components/DateText';

/**
 * The start of the earliest active term in `history` that begins after `today`, or null
 * when none is coming, such as for a member whose only term was canceled.
 *
 * @param history the member's terms, as `GET /me/membership` lists them.
 * @param today the day to count from, as `YYYY-MM-DD`; today unless given.
 */
export function upcomingTermStart(
  history: readonly MembershipTerm[] | undefined,
  today: IsoDate = todayIso(),
): IsoDate | null {
  const starts = (history ?? [])
    .filter((term) => term.status === 'active' && term.starts_on > today)
    .map((term) => term.starts_on)
    .sort();
  return starts[0] ?? null;
}
