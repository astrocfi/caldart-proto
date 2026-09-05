import { useEffect, useState } from 'react';

/** How long search-as-you-type waits before asking the server. */
export const SEARCH_DEBOUNCE_MS = 250;

/** `value`, but only after it has stopped changing for `delay` milliseconds. */
export function useDebounced<T>(value: T, delay: number = SEARCH_DEBOUNCE_MS): T {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);

  return settled;
}
