import { describe, expect, it } from 'vitest';

import type { Column } from './DataTable';
import {
  ACTIONS_MIN_WIDTH,
  arrangeColumns,
  fitColumns,
  LEAD_FLOOR_REM,
  needsFitting,
} from './tableFit';

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

describe('fitColumns on a phone', () => {
  const members: Column<object>[] = [
    column('pilot', { width: '4.25rem' }),
    column('name', { width: undefined, minWidth: '14rem', isIdentity: true }),
    column('dart', { width: undefined, minWidth: '10rem', dropOrder: 2 }),
    column('expires', { width: '10rem', keepInSight: true }),
    column('email', { width: undefined, minWidth: '14rem', dropOrder: 1 }),
  ];

  it('drops Email, then DART, before anything else', () => {
    expect(fitColumns(members, 30).map((shown) => shown.key)).toEqual(['pilot', 'name', 'expires']);
  });

  it('never narrows the name below the readable floor', () => {
    const name = fitColumns(members, 18).find((shown) => shown.key === 'name');
    expect(name?.minWidth).toBe(`${LEAD_FLOOR_REM}rem`);
  });

  it('narrows the identifying column rather than the first text column', () => {
    const fitted = fitColumns(
      [
        column('note', { width: undefined, minWidth: '12rem' }),
        column('name', { width: undefined, minWidth: '14rem', isIdentity: true }),
        column('actions', { width: '6rem', isActions: true }),
      ],
      30,
    );
    expect(fitted.map((shown) => shown.minWidth ?? shown.width)).toEqual([
      '12rem',
      '12rem',
      '6rem',
    ]);
  });
});

describe('arrangeColumns', () => {
  it('moves the actions column to the end', () => {
    const arranged = arrangeColumns([
      column('actions', { isActions: true }),
      column('name'),
      column('date'),
    ]);
    expect(arranged.map((shown) => shown.key)).toEqual(['name', 'date', 'actions']);
  });

  it('widens an actions column too narrow for an open confirmation', () => {
    const [actions] = arrangeColumns([column('actions', { isActions: true, width: '4rem' })]);
    expect(actions?.width).toBe(ACTIONS_MIN_WIDTH);
  });

  it('keeps an actions column already wide enough', () => {
    const [actions] = arrangeColumns([column('actions', { isActions: true, width: '14rem' })]);
    expect(actions?.width).toBe('14rem');
  });
});
