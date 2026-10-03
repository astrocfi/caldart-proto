import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { formatCountdown, secondsUntil, useSecondsUntil } from './countdown';

describe('formatCountdown', () => {
  it.each([
    [0, '0:00'],
    [9, '0:09'],
    [118, '1:58'],
    [600, '10:00'],
    [3725, '1:02:05'],
  ])('reads %i seconds as %s', (seconds, label) => {
    expect(formatCountdown(seconds)).toBe(label);
  });
});

describe('secondsUntil', () => {
  const now = new Date('2026-04-06T17:00:00Z');

  it('counts whole seconds up to the moment', () => {
    expect(secondsUntil('2026-04-06T17:01:58Z', now)).toBe(118);
  });

  it('rounds a part second up, so the label never shows 0:00 early', () => {
    expect(secondsUntil('2026-04-06T17:00:00.400Z', now)).toBe(1);
  });

  it('never goes below zero once the moment has passed', () => {
    expect(secondsUntil('2026-04-06T16:59:00Z', now)).toBe(0);
  });
});

describe('useSecondsUntil', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-06T17:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('ticks down once a second', () => {
    const { result } = renderHook(() => useSecondsUntil('2026-04-06T17:02:00Z'));
    const before = result.current;
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect([before, result.current]).toEqual([120, 117]);
  });

  it('answers null without a time', () => {
    const { result } = renderHook(() => useSecondsUntil(null));
    expect(result.current).toBeNull();
  });
});
