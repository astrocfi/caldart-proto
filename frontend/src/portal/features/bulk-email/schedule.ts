/**
 * Scheduled times, which a sender chooses in the site's own time zone and reads
 * back the same way everywhere: `10/04/2026 at 8:00 AM Pacific time`.
 */
import { datePartsIn, formatDateAt } from '@/portal/components/DateText';

/** The site's time zone, in which the server reads a time chosen without an offset. */
export const SITE_TIME_ZONE = 'America/Los_Angeles';

/** What the site's time zone is called on screen. */
export const SITE_TIME_ZONE_NAME = 'Pacific time';

/** One choice of the time box: its `HH:MM` value and its words, such as `8:00 AM`. */
export interface TimeChoice {
  value: string;
  label: string;
}

/** Every half hour of the day, `12:00 AM` to `11:30 PM`. */
export const TIME_CHOICES: readonly TimeChoice[] = Array.from({ length: 48 }, (_, index) =>
  timeChoice(`${String(Math.floor(index / 2)).padStart(2, '0')}:${index % 2 === 0 ? '00' : '30'}`),
);

/**
 * A time of day, `HH:MM` on the 24-hour clock, as the time box offers it.
 *
 * @param value the time, such as `13:30`.
 */
export function timeChoice(value: string): TimeChoice {
  const [hours = 0, minutes = 0] = value.split(':').map(Number);
  const period = hours < 12 ? 'AM' : 'PM';
  const hour = hours % 12 === 0 ? 12 : hours % 12;
  return { value, label: `${hour}:${String(minutes).padStart(2, '0')} ${period}` };
}

/**
 * A moment the server holds, such as an email's `start_at`, in the site's time zone:
 * `10/04/2026 at 8:00 AM Pacific time`.
 *
 * @param iso an ISO datetime with its offset.
 */
export function scheduledWords(iso: string | null): string {
  return `${formatDateAt(iso, SITE_TIME_ZONE)} ${SITE_TIME_ZONE_NAME}`;
}

/**
 * A time the sender chose and has not sent yet, `YYYY-MM-DDTHH:MM` in the site's
 * time zone, in the same words.
 *
 * @param chosen the date and time as the schedule's boxes give them.
 */
export function chosenWords(chosen: string): string {
  return `${formatDateAt(chosen)} ${SITE_TIME_ZONE_NAME}`;
}

/**
 * The date and the `HH:MM` time a moment falls on in the site's time zone, for the
 * schedule's boxes.
 *
 * @param iso an ISO datetime with its offset.
 */
export function sitePartsOf(iso: string): { date: string; time: string } {
  return datePartsIn(iso, SITE_TIME_ZONE);
}
