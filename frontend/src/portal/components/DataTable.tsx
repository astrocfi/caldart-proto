/**
 * The sortable table every list screen uses, with an optional filter bar, a row of
 * tools (the column chooser and the CSV/PDF exports) at its right, and an optional
 * pagination control under it.
 *
 * A single-line table fits itself to its container (`tableFit.ts`): it leaves out the
 * columns that matter least, one at a time, and on a phone narrows its identifying
 * column so the row's actions stay in sight.  No column is drawn narrower than its own
 * minimum.  A table that is still too wide scrolls sideways inside its card: it says
 * so in a line above it and with a shadow at the edge that hides more, its scroll box
 * becomes a named region a keyboard can focus and scroll, and its identifying column
 * stays pinned at the left so every row can still be told apart.
 */
import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { JSX, ReactNode, RefObject } from 'react';

import { Button } from './Button';
import { EmptyState } from './EmptyState';
import { Pagination } from './Pagination';
import type { PaginationSettings } from './Pagination';
import { arrangeColumns, DEFAULT_COLUMN_WIDTH, fitColumns, needsFitting } from './tableFit';
import { useTableScroll } from './useTableScroll';

export type SortDirection = 'asc' | 'desc';

export interface Column<Row> {
  /** Stable key; also the `ordering` value sent to the API. */
  key: string;
  /**
   * The heading.  An actions column may leave it blank: it is then headed
   * "Actions" for a screen reader alone.
   */
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
  /** Column width in rem, used when the table is in single-line mode. */
  width?: string;
  /**
   * The least a column of text takes in single-line mode, in rem, for a column that
   * shares out the room the fixed widths leave, such as a name or an email
   * address. The table never grows narrower than its fixed widths and these
   * minimums together, so on a narrow screen it scrolls inside its card instead
   * of squeezing these columns to nothing. Its cells start at the left edge.
   */
  minWidth?: string;
  /**
   * A column that matters less than the others, such as a type or a DART, which the
   * table leaves out while it would not fit its container. Columns go one at a time,
   * the lowest `dropOrder` first, until the rest fit, so the columns that matter, the
   * row's actions among them, stay in sight without scrolling. Every single-line column
   * gives its `width` or `minWidth` in rem, which is how the fit is reckoned.
   */
  dropOrder?: number;
  /**
   * A column that stays in sight on a screen too narrow for the table, such as a
   * status or a total: the identifying column then gives up its room, down to a
   * floor, so that the table's columns up to the last of these end within the
   * container.  An actions column always stays in sight.
   */
  keepInSight?: boolean;
  /**
   * The width a column that stays in sight takes on a screen too narrow for the
   * table, its content wrapping onto more lines, such as two buttons one above the
   * other.
   */
  narrowWidth?: string;
  /**
   * Let this column's words wrap onto more lines in single-line mode, for words that
   * must be read whole, such as a reason or a description.
   */
  wrap?: boolean;
  /**
   * The column that tells one row from another: a name, an N-number, a subject, or a
   * description.  It keeps a readable width before any other, stays pinned at the
   * left while the table scrolls sideways, and heads its row for a screen reader
   * (`th scope="row"`).  Its cells never wrap.
   */
  isIdentity?: boolean;
  /**
   * The row's buttons.  The table draws this column last, at least wide enough for an
   * open delete confirmation, never leaves it out, and heads it "Actions" for a screen
   * reader when `header` is blank.
   */
  isActions?: boolean;
  /**
   * Keep each cell on one line in any table, for a value that reads wrongly broken:
   * a receipt number, a phone number, a month.
   */
  noWrap?: boolean;
}

/**
 * The least width a single-line table takes: every fixed width and every minimum
 * added up, a column naming neither reckoned at the default width; `undefined`
 * when no column names a width or a minimum.
 */
export function tableMinWidth<Row>(columns: readonly Column<Row>[]): string | undefined {
  const isSized = columns.some((column) => (column.width ?? column.minWidth) !== undefined);
  if (!isSized) return undefined;
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

/** The class a cell of `column` carries: numeric or text, whether it wraps, pinned or actions. */
function cellClass<Row>(column: Column<Row>): string | undefined {
  const classes = [
    column.numeric ? 'numeric' : column.minWidth !== undefined ? 'data-table__text' : '',
    column.wrap ? 'data-table__wrap' : '',
    column.noWrap === true || column.isIdentity === true ? 'data-table__nowrap' : '',
    column.isIdentity === true ? 'data-table__identity' : '',
    column.isActions === true ? 'data-table__actions' : '',
  ].filter((name) => name !== '');
  return classes.length === 0 ? undefined : classes.join(' ');
}

/** The width of the element `ref` holds, in rem, measured again whenever it changes size. */
function useWidthRem(ref: RefObject<HTMLElement | null>, isMeasured: boolean): number | null {
  const [widthRem, setWidthRem] = useState<number | null>(null);
  useLayoutEffect(() => {
    const element = ref.current;
    if (element === null || !isMeasured || typeof ResizeObserver === 'undefined') {
      setWidthRem(null);
      return undefined;
    }
    const measure = (): void => {
      const rootPx = Number.parseFloat(getComputedStyle(document.documentElement).fontSize);
      setWidthRem(element.clientWidth / (Number.isNaN(rootPx) ? 16 : rootPx));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref, isMeasured]);
  return widthRem;
}

export interface DataTableProps<Row> {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string | number;
  caption?: string;
  /**
   * The name of the table's scroll box, which a keyboard can focus once the table
   * scrolls sideways; the caption unless given.
   */
  label?: string;
  /** Filter controls rendered above the table. */
  filters?: ReactNode;
  /**
   * Tools that act on the table as a whole, such as the column chooser, drawn on one
   * row at the right with the export buttons.
   */
  tools?: ReactNode;
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
  /** The next thing to do from an empty table, such as a **Reset filters** button. */
  emptyAction?: ReactNode;
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
  /**
   * Draw the pagination control under the table.  Moving to another page brings the
   * top of the table back into view.
   */
  pagination?: PaginationSettings;
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
  // Each direction compares in its own order rather than reversing the ascending
  // result, so rows that tie keep the order they arrived in either way.
  return [...rows].sort((a, b) =>
    direction === 'asc' ? compare(sortValue(a), sortValue(b)) : compare(sortValue(b), sortValue(a)),
  );
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

interface HeaderCellProps<Row> {
  column: Column<Row>;
  isSortable: boolean;
  /** The direction the table is sorted by this column, or null when it is not. */
  sorted: SortDirection | null;
  singleLine: boolean;
  onSort: () => void;
}

/** The arrow a sortable heading carries: up, down, or a faint both-ways while unsorted. */
function caretOf(sorted: SortDirection | null): string {
  if (sorted === 'asc') return '↑';
  if (sorted === 'desc') return '↓';
  return '↕';
}

/**
 * One column heading.  A sortable one is a button with an arrow, on the left of a
 * right-aligned heading so the words end over the figures; an unsortable one is
 * plain words with no arrow.  Only the sorted column carries `aria-sort`.
 */
function HeaderCell<Row>({
  column,
  isSortable,
  sorted,
  singleLine,
  onSort: handleSort,
}: HeaderCellProps<Row>): JSX.Element {
  const isBlankActions = column.isActions === true && column.header === '';
  const caret = (
    <span
      aria-hidden="true"
      className={
        sorted === null ? 'data-table__caret data-table__caret--idle' : 'data-table__caret'
      }
    >
      {caretOf(sorted)}
    </span>
  );
  let content: ReactNode = column.header;
  if (isBlankActions) content = <span className="visually-hidden">Actions</span>;
  else if (isSortable) {
    content = (
      <button type="button" className="data-table__sort" onClick={handleSort}>
        {column.numeric ? caret : null}
        {column.header}
        {column.numeric ? null : caret}
      </button>
    );
  }
  return (
    <th
      scope="col"
      className={cellClass(column)}
      style={singleLine ? columnStyle(column) : undefined}
      aria-sort={sorted === null ? undefined : sorted === 'asc' ? 'ascending' : 'descending'}
    >
      {content}
    </th>
  );
}

interface CellProps {
  isRowHeader: boolean;
  className: string | undefined;
  title: string | undefined;
  children: ReactNode;
}

/**
 * One body cell: a row header (`th scope="row"`) for the identifying column, so a
 * screen reader names each row by it, and an ordinary cell for the rest.
 */
function Cell({ isRowHeader, className, title, children }: CellProps): JSX.Element {
  if (isRowHeader) {
    return (
      <th scope="row" className={className} title={title}>
        {children}
      </th>
    );
  }
  return (
    <td className={className} title={title}>
      {children}
    </td>
  );
}

/** Names joined as a sentence lists them: "A", "A and B", "A, B, and C". */
function listNames(names: readonly string[]): string {
  if (names.length <= 2) return names.join(' and ');
  return `${names.slice(0, -1).join(', ')}, and ${names.at(-1) ?? ''}`;
}

/**
 * The line that names the columns the table left out to fit its container, or null
 * when it left none out.  With a column chooser beside the table it also offers
 * choosing fewer columns; the downloads keep the hidden columns either way.
 *
 * @param all every column the table would draw with room enough.
 * @param shown the columns it draws.
 * @param hasChooser whether the table's tools include a column chooser.
 * @returns the sentence, or null.
 */
export function hiddenColumnsNote<Row>(
  all: readonly Column<Row>[],
  shown: readonly Column<Row>[],
  hasChooser: boolean,
): string | null {
  const shownKeys = new Set(shown.map((column) => column.key));
  const hidden = all.filter((column) => !shownKeys.has(column.key)).map((column) => column.header);
  if (hidden.length === 0) return null;
  const verb = hidden.length === 1 ? 'is' : 'are';
  const advice = hasChooser
    ? 'Widen it, or choose fewer columns.'
    : 'Widen it to show every column.';
  return `${listNames(hidden)} ${verb} hidden to fit the window. ${advice}`;
}

/** The class of the box that holds the scroll box: whether it scrolls, and which way. */
function scrollClass(scroll: ReturnType<typeof useTableScroll>): string {
  return [
    'table-scroll',
    scroll.isOverflowing ? 'table-scroll--overflowing' : '',
    scroll.hasMoreLeft ? 'table-scroll--more-left' : '',
    scroll.hasMoreRight ? 'table-scroll--more-right' : '',
  ]
    .filter((name) => name !== '')
    .join(' ');
}

/** A sortable table with an optional filter bar, tools, exports, and pagination. */
export function DataTable<Row>({
  columns: givenColumns,
  rows,
  rowKey,
  caption,
  label,
  filters,
  tools,
  exportCsvUrl,
  exportPdfUrl,
  exportDisabledReason,
  emptyTitle = 'Nothing to show',
  emptyDescription,
  emptyAction,
  isLoading = false,
  singleLine = false,
  onSortChange,
  initialSort,
  sort,
  pagination,
}: DataTableProps<Row>): JSX.Element {
  const rootRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const allColumns = useMemo(() => arrangeColumns(givenColumns), [givenColumns]);
  const availableRem = useWidthRem(rootRef, singleLine && needsFitting(allColumns));
  const columns = fitColumns(allColumns, availableRem);
  const hiddenNote = hiddenColumnsNote(allColumns, columns, Boolean(tools));
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

  const isEmpty = sorted.length === 0 && !isLoading;
  const scroll = useTableScroll(scrollRef, !isEmpty);

  const isSortable = (column: Column<Row>): boolean =>
    column.sortable !== false &&
    column.isActions !== true &&
    (Boolean(column.sortValue) || Boolean(onSortChange));

  const toggle = (column: Column<Row>): void => {
    const nextDirection: SortDirection =
      sortKey === column.key && direction === 'asc' ? 'desc' : 'asc';
    setSortKey(column.key);
    setDirection(nextDirection);
    onSortChange?.(column.key, nextDirection);
  };

  const handlePageMoved = (): void => {
    rootRef.current?.scrollIntoView?.({ block: 'start' });
  };

  const hasExports = Boolean(exportCsvUrl || exportPdfUrl);
  const hasTools = hasExports || Boolean(tools);
  const regionName = label ?? caption ?? 'Table';

  return (
    <div ref={rootRef} className={singleLine ? 'data-table data-table--single-line' : 'data-table'}>
      {filters || hasTools ? (
        <div className="data-table__bar">
          {filters ? <div className="data-table__filters">{filters}</div> : null}
          {hasTools ? (
            <div className="cluster data-table__tools">
              {tools}
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

      {isEmpty ? (
        <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />
      ) : (
        <>
          {scroll.isOverflowing ? (
            <p className="muted data-table__scroll-hint">Scroll sideways to see every column.</p>
          ) : null}
          {hiddenNote === null ? null : (
            <p className="muted data-table__scroll-hint">{hiddenNote}</p>
          )}
          <div className={scrollClass(scroll)}>
            {/* The box scrolls a table wider than its card rather than widening the page.
              Once it does, a keyboard can reach it, and a screen reader hears its name. */}
            <div
              ref={scrollRef}
              className="table-wrap"
              role={scroll.isOverflowing ? 'region' : undefined}
              aria-label={scroll.isOverflowing ? regionName : undefined}
              tabIndex={scroll.isOverflowing ? 0 : undefined}
            >
              <table style={singleLine ? { minWidth: tableMinWidth(columns) } : undefined}>
                {caption ? <caption>{caption}</caption> : null}
                <thead>
                  <tr>
                    {columns.map((column) => (
                      <HeaderCell
                        key={column.key}
                        column={column}
                        isSortable={isSortable(column)}
                        sorted={sortKey === column.key ? direction : null}
                        singleLine={singleLine}
                        onSort={() => toggle(column)}
                      />
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((row) => (
                    <tr key={rowKey(row)}>
                      {columns.map((column) => {
                        const content = column.render(row);
                        return (
                          <Cell
                            key={column.key}
                            isRowHeader={column.isIdentity === true}
                            className={cellClass(column)}
                            title={typeof content === 'string' ? content : undefined}
                          >
                            {content}
                          </Cell>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
      {isLoading ? (
        <p className="muted data-table__loading" role="status">
          Loading…
        </p>
      ) : null}
      {pagination ? <Pagination {...pagination} onMoved={handlePageMoved} /> : null}
    </div>
  );
}
