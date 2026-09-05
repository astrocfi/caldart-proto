import { useEffect, useState } from 'react';

/**
 * `value`, but only after it has stopped changing for `delay` ms.
 *
 * Keeps a search box from firing a request per keystroke while still leaving
 * the input itself fully controlled.
 */
export function useDebounced<T>(value: T, delay = 250): T {
  const [settled, setSettled] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);

  return settled;
}
