import { useEffect, useState } from 'react';

/** How long search-as-you-type waits before asking the server. */
export const SEARCH_DEBOUNCE_MS: number = 250;

/**
 * `value`, but only after it has stopped changing for `delayMs` milliseconds.
 *
 * Keeps a search box from firing a request per keystroke while still leaving the
 * input itself fully controlled.  Each change restarts the wait, so only the last
 * value of a burst is returned, and unmounting cancels the wait, so no update
 * lands after the caller has gone.
 *
 * @param value the value to settle on.
 * @param delayMs how long `value` must hold still; defaults to `SEARCH_DEBOUNCE_MS`.
 * @returns the most recent value that held still for `delayMs`.
 */
export function useDebounced<T>(value: T, delayMs: number = SEARCH_DEBOUNCE_MS): T {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delayMs);
    return () => window.clearTimeout(timer);
  }, [value, delayMs]);

  return settled;
}
