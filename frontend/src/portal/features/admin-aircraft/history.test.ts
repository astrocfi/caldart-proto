import { describe, expect, it } from 'vitest';

import type { AircraftChange } from '@/portal/api/types';
import { actorName, changeLine, fieldLabel, lastUpdatedLine } from './history';

/**
 * A stamp with no zone on it, which reads as local time wherever the suite
 * runs, so an assertion on the clock does not depend on the runner's zone.
 */
const CHANGED_AT = '2026-09-01T12:34:00';

function makeChange(overrides: Partial<AircraftChange> = {}): AircraftChange {
  return {
    id: 1,
    changed_at: CHANGED_AT,
    changed_by: { id: 4, name: 'Dana Fiske' },
    kind: 'updated',
    fields: ['insurance_carrier'],
    ...overrides,
  };
}

describe('fieldLabel', () => {
  it('names a register column the way the form labels it', () => {
    expect(fieldLabel('insurance_liability_per_occurrence_cents')).toBe('liability per occurrence');
  });

  it('falls back to the column name a label was never written for', () => {
    expect(fieldLabel('some_new_column')).toBe('some new column');
  });
});

describe('actorName', () => {
  it('names the account behind a write', () => {
    expect(actorName({ id: 4, name: 'Dana Fiske' })).toBe('Dana Fiske');
  });

  it('calls a write with no account behind it the seed', () => {
    expect(actorName(null)).toBe('the seed');
  });
});

describe('changeLine', () => {
  it('reads a creation as the date, the name, and created', () => {
    expect(changeLine(makeChange({ kind: 'created', fields: [] }))).toBe(
      '2026/09/01 12:34 · Dana Fiske · created',
    );
  });

  it('names every column an update moved', () => {
    expect(changeLine(makeChange({ fields: ['insurance_carrier', 'insurance_expiration'] }))).toBe(
      '2026/09/01 12:34 · Dana Fiske · updated carrier, insurance expiry',
    );
  });

  it('says only updated when an update names no column', () => {
    expect(changeLine(makeChange({ fields: [], changed_by: null }))).toBe(
      '2026/09/01 12:34 · the seed · updated',
    );
  });
});

describe('lastUpdatedLine', () => {
  it('names the date and the account behind the last write', () => {
    expect(lastUpdatedLine(CHANGED_AT, { id: 4, name: 'Dana Fiske' })).toBe(
      'Last updated 2026/09/01 by Dana Fiske',
    );
  });

  it('gives the date alone when nobody is recorded', () => {
    expect(lastUpdatedLine(CHANGED_AT, null)).toBe('Last updated 2026/09/01');
  });
});
