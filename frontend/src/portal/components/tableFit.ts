/**
 * How a single-line `DataTable` fits its container.
 *
 * A table wider than its container first leaves out the columns that matter least,
 * one at a time, the lowest `dropOrder` first, until the rest fit. A table still too
 * wide, as on a phone, scrolls sideways inside its card, but keeps the columns up to
 * its last `keepInSight` column (the row's actions) in sight where it can: those
 * columns take their `narrowWidth` and wrap, and the identifying column gives up its
 * room, down to `LEAD_FLOOR_REM`, which is still enough to read a name by. No column
 * is ever drawn narrower than its own width or minimum, so none shrinks to nothing.
 */
import type { Column } from './DataTable';

/** What a column without a width or a minimum is reckoned at. */
export const DEFAULT_COLUMN_WIDTH = '6rem';

/**
 * The least the identifying column, such as a name, keeps on the narrowest screen:
 * room for a first name and the start of a surname.
 */
export const LEAD_FLOOR_REM = 8;

/**
 * The least an actions column takes: room for an open delete confirmation, its
 * danger button and **Cancel** side by side, so neither is cut off.
 */
export const ACTIONS_MIN_WIDTH = '10rem';

/** `12rem` as 12; the default column width for anything else. */
export function remOf(length: string | undefined): number {
  const match = /^(\d+(?:\.\d+)?)rem$/.exec(length ?? DEFAULT_COLUMN_WIDTH);
  return match ? Number(match[1]) : remOf(DEFAULT_COLUMN_WIDTH);
}

/** What a column takes in the reckoning: its fixed width, or its minimum. */
function widthOf<Row>(column: Column<Row>): number {
  return remOf(column.width ?? column.minWidth);
}

/** The columns' widths added up, in rem. */
function total<Row>(columns: readonly Column<Row>[]): number {
  return columns.reduce((sum, column) => sum + widthOf(column), 0);
}

/** Whether a column stays in sight on a narrow screen: one marked so, or the actions. */
function staysInSight<Row>(column: Column<Row>): boolean {
  return column.keepInSight === true || column.isActions === true;
}

/**
 * The columns in the order the table draws them: as given, except that the actions
 * column always comes last, wide enough for its open confirmation.
 *
 * @param columns the table's columns, as the screen lists them.
 * @returns the same columns, the actions moved to the end and given their least width.
 */
export function arrangeColumns<Row>(columns: readonly Column<Row>[]): Column<Row>[] {
  const actions = columns
    .filter((column) => column.isActions === true)
    .map((column) => {
      const width = column.width ?? column.minWidth;
      const isTooNarrow = width === undefined || remOf(width) < remOf(ACTIONS_MIN_WIDTH);
      return isTooNarrow ? { ...column, width: ACTIONS_MIN_WIDTH, minWidth: undefined } : column;
    });
  return [...columns.filter((column) => column.isActions !== true), ...actions];
}

/**
 * `columns` with the identifying column moved to the front, where it stays pinned as the
 * table scrolls, for a table whose columns follow a report's export order, which leads
 * with something else (the roles report with Role, the email log with Sent).
 *
 * @param columns the table's columns, as the report lists them.
 * @returns the same columns, the identifying one first.
 */
export function identityFirst<Row>(columns: readonly Column<Row>[]): Column<Row>[] {
  return [
    ...columns.filter((column) => column.isIdentity === true),
    ...columns.filter((column) => column.isIdentity !== true),
  ];
}

/** Whether `columns` give the table anything to fit: a column to drop or to keep in sight. */
export function needsFitting<Row>(columns: readonly Column<Row>[]): boolean {
  return columns.some((column) => column.dropOrder !== undefined || staysInSight(column));
}

/**
 * The columns to show in a container `availableRem` wide, in their order: every
 * column when it is unknown (`null`) or the table fits; else the table less its
 * droppable columns, one at a time, until it fits; and, when even that is too wide,
 * the columns that stay in sight at their `narrowWidth`, wrapping, with the
 * identifying column narrowed so that they end within the container.
 *
 * @param columns the table's columns, in order.
 * @param availableRem the container's width in rem, or null when it is not measured.
 * @returns the columns to draw, some of them copies with a changed width.
 */
export function fitColumns<Row>(
  columns: readonly Column<Row>[],
  availableRem: number | null,
): Column<Row>[] {
  if (availableRem === null) return [...columns];
  const droppable = columns
    .filter((column) => column.dropOrder !== undefined)
    .sort((a, b) => (a.dropOrder ?? 0) - (b.dropOrder ?? 0));
  let shown = [...columns];
  for (const column of droppable) {
    if (total(shown) <= availableRem) break;
    shown = shown.filter((kept) => kept !== column);
  }
  if (total(shown) <= availableRem) return shown;
  return keepActionsInSight(shown, availableRem);
}

/** The index of the column a narrow table narrows: the identifying one, else the first text column. */
function leadIndex<Row>(columns: readonly Column<Row>[]): number {
  const identity = columns.findIndex((column) => column.isIdentity === true);
  if (identity !== -1) return identity;
  return columns.findIndex((column) => column.minWidth !== undefined);
}

/**
 * `columns`, too wide for `availableRem`, with each column that stays in sight at
 * its `narrowWidth` and wrapping, and the identifying column narrowed, down to
 * `LEAD_FLOOR_REM`, so that everything up to the last such column fits.
 */
function keepActionsInSight<Row>(columns: Column<Row>[], availableRem: number): Column<Row>[] {
  const narrowed = columns.map((column) =>
    staysInSight(column) && column.narrowWidth !== undefined
      ? { ...column, width: column.narrowWidth, wrap: true }
      : column,
  );
  const lead = leadIndex(narrowed);
  const last = narrowed.map(staysInSight).lastIndexOf(true);
  if (lead === -1 || last <= lead) return narrowed;
  const leadColumn = narrowed[lead] as Column<Row>;
  const others = total(narrowed.slice(lead + 1, last + 1));
  const before = total(narrowed.slice(0, lead));
  const room = Math.max(LEAD_FLOOR_REM, Math.floor((availableRem - others - before) * 4) / 4);
  if (room >= widthOf(leadColumn)) return narrowed;
  const narrowedLead =
    leadColumn.width !== undefined
      ? { ...leadColumn, width: `${room}rem` }
      : { ...leadColumn, minWidth: `${room}rem` };
  return narrowed.map((column, index) => (index === lead ? narrowedLead : column));
}
