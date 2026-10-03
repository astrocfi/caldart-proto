/**
 * The undo window's countdown, and how long things take, in words.
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
 * `seconds` as a countdown, such as `1 min 58 s`, `45 s`, or `2 min`.
 *
 * @param seconds a whole number of seconds, zero or more.
 */
export function formatCountdown(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(whole / 60);
  const rest = whole % 60;
  if (minutes === 0) return `${rest} s`;
  if (rest === 0) return `${minutes} min`;
  return `${minutes} min ${rest} s`;
}

/**
 * `seconds` as a length of time in words, such as `2 minutes` or `1 minute 30 seconds`.
 *
 * @param seconds a whole number of seconds, zero or more.
 */
export function formatDuration(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(whole / 60);
  const rest = whole % 60;
  const minuteWords = minutes === 1 ? '1 minute' : `${minutes} minutes`;
  const secondWords = rest === 1 ? '1 second' : `${rest} seconds`;
  if (minutes === 0) return secondWords;
  if (rest === 0) return minuteWords;
  return `${minuteWords} ${secondWords}`;
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
