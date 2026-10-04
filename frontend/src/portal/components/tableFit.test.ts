import { describe, expect, it } from 'vitest';

import type { Column } from './DataTable';
import { fitColumns, LEAD_FLOOR_REM, needsFitting } from './tableFit';

/** A column of `width` rem, with any other settings given. */
function column(key: string, settings: Partial<Column<object>> = {}): Column<object> {
  return { key, header: key, width: '5rem', render: () => key, ...settings };
}

const COLUMNS: Column<object>[] = [
  column('subject', { width: undefined, minWidth: '14rem' }),
  column('actions', { width: '9rem', keepInSight: true, narrowWidth: '6rem' }),
  column('type', { dropOrder: 1 }),
  column('dart', { dropOrder: 2 }),
  column('status'),
  column('from', { dropOrder: 3 }),
];

/** The keys of the columns `fitColumns` shows at `rem`. */
function keysAt(rem: number | null): string[] {
  return fitColumns(COLUMNS, rem).map((shown) => shown.key);
}

describe('fitColumns', () => {
  it('shows every column when the container is not measured', () => {
    expect(keysAt(null)).toHaveLength(6);
  });

  it('shows every column when they all fit', () => {
    expect(keysAt(48)).toEqual(['subject', 'actions', 'type', 'dart', 'status', 'from']);
  });

  it('leaves out the lowest drop order first, one column at a time', () => {
    expect(keysAt(42)).toEqual(['subject', 'actions', 'dart', 'status', 'from']);
  });

  it('keeps the last column to drop while the rest fit', () => {
    expect(keysAt(37)).toEqual(['subject', 'actions', 'status', 'from']);
  });

  it('leaves out every droppable column when even that is too wide', () => {
    expect(keysAt(30)).toEqual(['subject', 'actions', 'status']);
  });

  it('narrows the actions and the leading column so the actions end in sight', () => {
    const fitted = fitColumns(COLUMNS, 19);
    expect([fitted[0]?.minWidth, fitted[1]?.width, fitted[1]?.wrap]).toEqual([
      '13rem',
      '6rem',
      true,
    ]);
  });

  it('keeps the leading column at its floor on the narrowest screen', () => {
    expect(fitColumns(COLUMNS, 8)[0]?.minWidth).toBe(`${LEAD_FLOOR_REM}rem`);
  });
});

describe('needsFitting', () => {
  it('needs no measuring for a table with nothing to drop or keep in sight', () => {
    expect(needsFitting([column('a'), column('b')])).toBe(false);
  });
});
