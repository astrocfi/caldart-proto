/**
 * How a single-line `DataTable` fits its container.
 *
 * A table wider than its container first leaves out the columns that matter least,
 * one at a time, the lowest `dropOrder` first, until the rest fit. A table still too
 * wide, as on a phone, scrolls sideways, but keeps the columns up to its last
 * `keepInSight` column (the row's actions) in sight: those columns take their
 * `narrowWidth` and wrap, and the leading text column gives up its room, down to
 * `LEAD_FLOOR_REM`.
 */
import type { Column } from './DataTable';

/** What a column without a width or a minimum is reckoned at. */
export const DEFAULT_COLUMN_WIDTH = '6rem';

/** The least a leading text column, such as a name, keeps on the narrowest screen. */
export const LEAD_FLOOR_REM = 5;

/** `12rem` as 12; the default column width for anything else. */
function remOf(length: string | undefined): number {
  const match = /^(\d+(?:\.\d+)?)rem$/.exec(length ?? DEFAULT_COLUMN_WIDTH);
  return match ? Number(match[1]) : 6;
}

/** What a column takes in the reckoning: its fixed width, or its minimum. */
function widthOf<Row>(column: Column<Row>): number {
  return remOf(column.width ?? column.minWidth);
}

/** The columns' widths added up, in rem. */
function total<Row>(columns: readonly Column<Row>[]): number {
  return columns.reduce((sum, column) => sum + widthOf(column), 0);
}

/** Whether `columns` give the table anything to fit: a column to drop or to keep in sight. */
export function needsFitting<Row>(columns: readonly Column<Row>[]): boolean {
  return columns.some((column) => column.dropOrder !== undefined || column.keepInSight === true);
}

/**
 * The columns to show in a container `availableRem` wide, in their order: every
 * column when it is unknown (`null`) or the table fits; else the table less its
 * droppable columns, one at a time, until it fits; and, when even that is too wide,
 * the `keepInSight` columns at their `narrowWidth`, wrapping, with the leading text
 * column narrowed so that they end within the container.
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

/**
 * `columns`, too wide for `availableRem`, with each `keepInSight` column at its
 * `narrowWidth` and wrapping, and the leading text column narrowed, down to
 * `LEAD_FLOOR_REM`, so that everything up to the last such column fits.
 */
function keepActionsInSight<Row>(columns: Column<Row>[], availableRem: number): Column<Row>[] {
  const narrowed = columns.map((column) =>
    column.keepInSight === true && column.narrowWidth !== undefined
      ? { ...column, width: column.narrowWidth, wrap: true }
      : column,
  );
  const lead = narrowed.findIndex((column) => column.minWidth !== undefined);
  const last = narrowed.map((column) => column.keepInSight === true).lastIndexOf(true);
  if (lead === -1 || last <= lead) return narrowed;
  const leadColumn = narrowed[lead] as Column<Row>;
  const others = total(narrowed.slice(lead + 1, last + 1));
  const room = Math.max(LEAD_FLOOR_REM, Math.floor((availableRem - others) * 4) / 4);
  if (room >= widthOf(leadColumn)) return narrowed;
  return narrowed.map((column, index) =>
    index === lead ? { ...column, minWidth: `${room}rem` } : column,
  );
}
