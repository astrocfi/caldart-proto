/**
 * The sortable table every admin screen uses, with an optional
 * filter bar and CSV/PDF export buttons.
 *
 * A single-line table whose columns would not all fit its container leaves out the
 * columns marked `wideOnly`, so the rest, and the row's actions, stay in sight.
 */
import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { JSX, ReactNode, RefObject } from 'react';

import { Button } from './Button';
import { EmptyState } from './EmptyState';

export type SortDirection = 'asc' | 'desc';

export interface Column<Row> {
  /** Stable key; also the `ordering` value sent to the API. */
  key: string;
  header: string;
  render: (row: Row) => ReactNode;
  /** Value used for client-side sorting. Omit to make the column unsortable. */
  sortValue?: (row: Row) => string | number | null;
  /**
   * Set false to keep a column unsortable under server-side sorting, where
   * every column is sortable by default. Use it for a column the API has no
   * `ordering` value for.
   */
  sortable?: boolean;
  /** Right-align and use tabular figures. */
  numeric?: boolean;
  /** Column width, used when the table is in single-line mode. */
  width?: string;
  /**
   * The least a column of text takes in single-line mode, for a column that
   * shares out the room the fixed widths leave, such as a name or an email
   * address. The table never grows narrower than its fixed widths and these
   * minimums together, so on a narrow screen it scrolls inside its card instead
   * of squeezing these columns to nothing. Its cells start at the left edge.
   */
  minWidth?: string;
  /**
   * A column that matters less than the others, such as a type or a DART, which the
   * table leaves out while it would not fit its container with every column shown,
   * so the columns that matter, the row's actions among them, stay in sight without
   * scrolling. It needs `width` or `minWidth` in rem, as every single-line column has.
   */
  wideOnly?: boolean;
  /**
   * Let this column's words wrap onto more lines in single-line mode, for words that
   * must be read whole, such as a reason or a description.
   */
  wrap?: boolean;
}

/** What a column without a width or a minimum is reckoned at, for the table's minimum. */
const DEFAULT_COLUMN_WIDTH = '6rem';

/**
 * The least width a single-line table takes: every fixed width and every minimum
 * added up, or `undefined` when no column names a minimum.
 */
export function tableMinWidth<Row>(columns: readonly Column<Row>[]): string | undefined {
  if (!columns.some((column) => column.minWidth !== undefined)) return undefined;
  const parts = columns.map((column) => column.width ?? column.minWidth ?? DEFAULT_COLUMN_WIDTH);
  return `calc(${parts.join(' + ')})`;
}

/**
 * A single-line column's width: its fixed width, or its minimum, which a table with
 * room to spare widens in proportion with the others.
 */
function columnStyle<Row>(column: Column<Row>): { width: string } | undefined {
  const width = column.width ?? column.minWidth;
  return width === undefined ? undefined : { width };
}

/** The class a cell of `column` carries: numeric or text, and whether it wraps. */
function cellClass<Row>(column: Column<Row>): string | undefined {
  const classes = [
    column.numeric ? 'numeric' : column.minWidth !== undefined ? 'data-table__text' : '',
    column.wrap ? 'data-table__wrap' : '',
  ].filter((name) => name !== '');
  return classes.length === 0 ? undefined : classes.join(' ');
}

/** `12rem` as 12; null for any other length. */
function remOf(length: string): number | null {
  const match = /^(\d+(?:\.\d+)?)rem$/.exec(length);
  return match ? Number(match[1]) : null;
}

/**
 * The least width, in rem, the table takes with every column shown; null when no
 * column is `wideOnly`, or when a width is not given in rem.
 */
export function fullWidthRem<Row>(columns: readonly Column<Row>[]): number | null {
  if (!columns.some((column) => column.wideOnly === true)) return null;
  const widths = columns.map((column) =>
    remOf(column.width ?? column.minWidth ?? DEFAULT_COLUMN_WIDTH),
  );
  if (widths.some((width) => width === null)) return null;
  return widths.reduce<number>((total, width) => total + (width ?? 0), 0);
}

/**
 * The columns to show in a container `isWide` or not: every column when it is, and
 * all but the `wideOnly` ones when it is not.
 */
export function shownColumns<Row>(columns: Column<Row>[], isWide: boolean): Column<Row>[] {
  return isWide ? columns : columns.filter((column) => column.wideOnly !== true);
}

/**
 * Whether the element `ref` holds is at least `rem` wide, measured again whenever it
 * changes size. True when `rem` is null, and where the browser cannot measure.
 */
function useIsAtLeast(ref: RefObject<HTMLElement | null>, rem: number | null): boolean {
  const [isWide, setIsWide] = useState(true);
  useLayoutEffect(() => {
    const element = ref.current;
    if (element === null || rem === null || typeof ResizeObserver === 'undefined') {
      setIsWide(true);
      return undefined;
    }
    const measure = (): void => {
      const rootPx = Number.parseFloat(getComputedStyle(document.documentElement).fontSize);
      setIsWide(element.clientWidth >= rem * (Number.isNaN(rootPx) ? 16 : rootPx));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref, rem]);
  return isWide;
}

export interface DataTableProps<Row> {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string | number;
  caption?: string;
  /** Filter controls rendered above the table. */
  filters?: ReactNode;
  /** Export hrefs; the buttons only appear when a URL is given. */
  exportCsvUrl?: string;
  exportPdfUrl?: string;
  /**
   * Why the exports cannot be had right now.  When set, each export given a URL
   * is drawn as a disabled button carrying this as its `title`, in the place the
   * link would take, so the control stays where the eye expects it.
   */
  exportDisabledReason?: string;
  emptyTitle?: string;
  emptyDescription?: ReactNode;
  isLoading?: boolean;
  /**
   * Keep every cell on one line, cutting anything too long with an ellipsis.
   * The full value stays reachable: a cell whose content is plain text also
   * carries it as a `title`.
   */
  singleLine?: boolean;
  /** Take sorting server-side instead: called with key and direction. */
  onSortChange?: (key: string, direction: SortDirection) => void;
  initialSort?: { key: string; direction: SortDirection };
  /**
   * The order to show, for a table whose order is kept outside it (such as in
   * the address): the arrow follows this rather than the table's own state, so
   * it stays right when the order changes from elsewhere.  Overrides `initialSort`.
   */
  sort?: { key: string; direction: SortDirection };
}

function compare(a: string | number | null, b: string | number | null): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  return String(a).localeCompare(String(b), 'en', { numeric: true, sensitivity: 'base' });
}

/** Sorts `rows` by `column`'s `sortValue`, or returns them unchanged when it has none. */
export function sortRows<Row>(
  rows: Row[],
  column: Column<Row> | undefined,
  direction: SortDirection,
): Row[] {
  if (!column?.sortValue) return rows;
  const sortValue = column.sortValue;
  const sorted = [...rows].sort((a, b) => compare(sortValue(a), sortValue(b)));
  return direction === 'asc' ? sorted : sorted.reverse();
}

/** One export: a link to the download, or a disabled button saying why there is none. */
function ExportLink({
  href,
  disabledReason,
  children,
}: {
  href: string;
  disabledReason: string | undefined;
  children: string;
}): JSX.Element {
  if (disabledReason !== undefined) {
    return (
      <Button variant="quiet" small disabled title={disabledReason}>
        {children}
      </Button>
    );
  }
  return (
    <a className="button button--quiet button--small" href={href}>
      {children}
    </a>
  );
}

/** A sortable table with an optional filter bar and CSV/PDF export buttons. */
export function DataTable<Row>({
  columns: allColumns,
  rows,
  rowKey,
  caption,
  filters,
  exportCsvUrl,
  exportPdfUrl,
  exportDisabledReason,
  emptyTitle = 'Nothing to show',
  emptyDescription,
  isLoading = false,
  singleLine = false,
  onSortChange,
  initialSort,
  sort,
}: DataTableProps<Row>): JSX.Element {
  const rootRef = useRef<HTMLDivElement>(null);
  const isWide = useIsAtLeast(
    rootRef,
    singleLine ? fullWidthRem(allColumns) : null,
  );
  const columns = shownColumns(allColumns, isWide);
  const [ownKey, setSortKey] = useState<string | null>(initialSort?.key ?? null);
  const [ownDirection, setDirection] = useState<SortDirection>(initialSort?.direction ?? 'asc');
  const sortKey = sort ? sort.key : ownKey;
  const direction = sort ? sort.direction : ownDirection;

  const sorted = useMemo(() => {
    if (onSortChange || !sortKey) return rows;
    return sortRows(
      rows,
      allColumns.find((column) => column.key === sortKey),
      direction,
    );
  }, [rows, allColumns, sortKey, direction, onSortChange]);

  const toggle = (column: Column<Row>): void => {
    if (column.sortable === false) return;
    if (!column.sortValue && !onSortChange) return;
    const nextDirection: SortDirection =
      sortKey === column.key && direction === 'asc' ? 'desc' : 'asc';
    setSortKey(column.key);
    setDirection(nextDirection);
    onSortChange?.(column.key, nextDirection);
  };

  const hasExports = Boolean(exportCsvUrl || exportPdfUrl);

  return (
    <div
      ref={rootRef}
      className={singleLine ? 'data-table data-table--single-line' : 'data-table'}
    >
      {filters || hasExports ? (
        <div className="data-table__bar">
          <div className="data-table__filters">{filters}</div>
          {hasExports ? (
            <div className="cluster data-table__exports">
              {exportCsvUrl ? (
                <ExportLink href={exportCsvUrl} disabledReason={exportDisabledReason}>
                  Export CSV
                </ExportLink>
              ) : null}
              {exportPdfUrl ? (
                <ExportLink href={exportPdfUrl} disabledReason={exportDisabledReason}>
                  Export PDF
                </ExportLink>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {sorted.length === 0 && !isLoading ? (
        <EmptyState title={emptyTitle} description={emptyDescription} />
      ) : (
        // `.table-wrap` scrolls a table that is wider than its container,
        // rather than widening the page around it.
        <div className="table-wrap">
          <table style={singleLine ? { minWidth: tableMinWidth(columns) } : undefined}>
            {caption ? <caption>{caption}</caption> : null}
            <thead>
              <tr>
                {columns.map((column) => {
                  const sortable =
                    column.sortable !== false &&
                    (Boolean(column.sortValue) || Boolean(onSortChange));
                  const isSorted = sortKey === column.key;
                  return (
                    <th
                      key={column.key}
                      scope="col"
                      className={cellClass(column)}
                      style={singleLine ? columnStyle(column) : undefined}
                      aria-sort={
                        isSorted ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'
                      }
                    >
                      {sortable ? (
                        <button
                          type="button"
                          className="data-table__sort"
                          onClick={() => toggle(column)}
                        >
                          {column.header}
                          <span aria-hidden="true" className="data-table__caret">
                            {isSorted ? (direction === 'asc' ? '↑' : '↓') : ''}
                          </span>
                        </button>
                      ) : (
                        column.header
                      )}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {sorted.map((row) => (
                <tr key={rowKey(row)}>
                  {columns.map((column) => {
                    const content = column.render(row);
                    return (
                      <td
                        key={column.key}
                        className={cellClass(column)}
                        title={typeof content === 'string' ? content : undefined}
                      >
                        {content}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {isLoading ? (
        <p className="muted data-table__loading" role="status">
          Loading…
        </p>
      ) : null}
    </div>
  );
}
