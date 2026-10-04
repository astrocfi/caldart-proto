import { describe, expect, it } from 'vitest';

import { isItemHeld, isLapsed } from './held';
import type { HeldFacts } from './held';

const PILOT: HeldFacts = {
  pilot_certificate_type: 'private',
  medical_type: 'third',
  photo_id_type: 'passport',
};

const TODAY = new Date('2026-06-01T09:00:00');

describe('isItemHeld', () => {
  it.each(['certificate', 'medical', 'photo_id'] as const)('reads a %s on file as held', (item) => {
    expect(isItemHeld(item, PILOT)).toBe(true);
  });

  it.each([
    ['certificate', { pilot_certificate_type: 'none' }],
    ['medical', { medical_type: 'none' }],
    ['photo_id', { photo_id_type: 'not_provided' }],
  ] as const)('reads a %s marked none as not held', (item, override) => {
    expect(isItemHeld(item, { ...PILOT, ...override })).toBe(false);
  });
});

describe('isLapsed', () => {
  it('reads yesterday as lapsed', () => {
    expect(isLapsed('2026-05-31', TODAY)).toBe(true);
  });

  it('counts a date as current through its own day', () => {
    expect(isLapsed('2026-06-01', TODAY)).toBe(false);
  });

  it('never reads a missing date as lapsed', () => {
    expect(isLapsed(null, TODAY)).toBe(false);
  });
});
