import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { SEARCH_DEBOUNCE_MS, useDebounced } from './useDebounced';

const CUSTOM_DELAY_MS = 500;

/** Render the hook over a changing `value`, so `rerender` can supply the next one. */
function renderDebounced(initial: string, delayMs?: number) {
  return renderHook(({ value }) => useDebounced(value, delayMs), {
    initialProps: { value: initial },
  });
}

describe('useDebounced', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('waits a quarter of a second by default', () => {
    expect(SEARCH_DEBOUNCE_MS).toBe(250);
  });

  it('returns the initial value immediately', () => {
    const { result } = renderDebounced('first');

    expect(result.current).toBe('first');
  });

  it('keeps the previous value one millisecond before the delay', () => {
    const { result, rerender } = renderDebounced('first');

    rerender({ value: 'second' });
    act(() => {
      vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS - 1);
    });

    expect(result.current).toBe('first');
  });

  it('adopts the new value once the delay has passed', () => {
    const { result, rerender } = renderDebounced('first');

    rerender({ value: 'second' });
    act(() => {
      vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS);
    });

    expect(result.current).toBe('second');
  });

  it('restarts the wait on every change, so only the last value lands', () => {
    const { result, rerender } = renderDebounced('first');

    rerender({ value: 'second' });
    act(() => {
      vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS - 1);
    });
    rerender({ value: 'third' });
    act(() => {
      vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS - 1);
    });

    expect(result.current).toBe('first');

    act(() => {
      vi.advanceTimersByTime(1);
    });

    expect(result.current).toBe('third');
  });

  it('honors a custom delay', () => {
    const { result, rerender } = renderDebounced('first', CUSTOM_DELAY_MS);

    rerender({ value: 'second' });
    act(() => {
      vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS);
    });

    expect(result.current).toBe('first');

    act(() => {
      vi.advanceTimersByTime(CUSTOM_DELAY_MS - SEARCH_DEBOUNCE_MS);
    });

    expect(result.current).toBe('second');
  });

  it('cancels a pending update when the component unmounts', () => {
    const { result, rerender, unmount } = renderDebounced('first');

    rerender({ value: 'second' });
    unmount();

    expect(vi.getTimerCount()).toBe(0);

    act(() => {
      vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS);
    });

    expect(result.current).toBe('first');
  });
});
