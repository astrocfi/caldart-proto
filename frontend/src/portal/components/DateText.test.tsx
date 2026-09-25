/** The date helpers every screen that reads or offers a date shares. */
import { describe, expect, it } from 'vitest';

import { todayIso } from './DateText';

describe('todayIso', () => {
  it('writes the reader’s own day as the date box wants it', () => {
    expect(todayIso(new Date(2026, 8, 4))).toBe('2026-09-04');
  });
});
