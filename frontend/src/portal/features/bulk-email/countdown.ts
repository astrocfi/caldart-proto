/**
 * The undo window's countdown: how long until a queued email starts, as `m:ss`.
 *
 * The time comes from the email's `start_at` and the reader's own clock, ticking
 * once a second, so the label moves smoothly between the screen's reads of the
 * email.
 */
import { useEffect, useState } from 'react';

/** How often the countdown ticks. */
const TICK_MS = 1000;

/**
 * Whole seconds from `now` until `iso`, never below zero.
 *
 * @param iso the moment counted down to.
 * @param now the moment counted from.
 */
export function secondsUntil(iso: string, now: Date): number {
  const target = new Date(iso).getTime();
  if (Number.isNaN(target)) return 0;
  return Math.max(0, Math.ceil((target - now.getTime()) / 1000));
}

/**
 * `seconds` as `m:ss`, such as `1:58`; an hour or more reads `h:mm:ss`.
 *
 * @param seconds a whole number of seconds, zero or more.
 */
export function formatCountdown(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const rest = String(whole % 60).padStart(2, '0');
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, '0')}:${rest}`;
  return `${minutes}:${rest}`;
}

/**
 * The seconds left until `iso`, read again once a second; null without a time.
 *
 * @param iso the moment counted down to, or null for none.
 */
export function useSecondsUntil(iso: string | null): number | null {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    if (iso === null) return undefined;
    const timer = window.setInterval(() => setNow(new Date()), TICK_MS);
    return () => window.clearInterval(timer);
  }, [iso]);

  return iso === null ? null : secondsUntil(iso, now);
}
