/**
 * The sortable table every admin screen uses, with an optional
 * filter bar and CSV/PDF export buttons.
 */
import { useMemo, useState } from 'react';
import type { JSX, ReactNode } from 'react';

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

/** A sortable table with an optional filter bar and CSV/PDF export buttons. */
export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  caption,
  filters,
  exportCsvUrl,
  exportPdfUrl,
  emptyTitle = 'Nothing to show',
  emptyDescription,
  isLoading = false,
  singleLine = false,
  onSortChange,
  initialSort,
}: DataTableProps<Row>): JSX.Element {
  const [sortKey, setSortKey] = useState<string | null>(initialSort?.key ?? null);
  const [direction, setDirection] = useState<SortDirection>(initialSort?.direction ?? 'asc');

  const sorted = useMemo(() => {
    if (onSortChange || !sortKey) return rows;
    return sortRows(
      rows,
      columns.find((column) => column.key === sortKey),
      direction,
    );
  }, [rows, columns, sortKey, direction, onSortChange]);

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
    <div className={singleLine ? 'data-table data-table--single-line' : 'data-table'}>
      {filters || hasExports ? (
        <div className="data-table__bar">
          <div className="data-table__filters">{filters}</div>
          {hasExports ? (
            <div className="cluster data-table__exports">
              {exportCsvUrl ? (
                <a className="button button--quiet button--small" href={exportCsvUrl}>
                  Export CSV
                </a>
              ) : null}
              {exportPdfUrl ? (
                <a className="button button--quiet button--small" href={exportPdfUrl}>
                  Export PDF
                </a>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {sorted.length === 0 && !isLoading ? (
        <EmptyState title={emptyTitle} description={emptyDescription} />
      ) : (
        <div className="table-wrap">
          <table>
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
                      className={column.numeric ? 'numeric' : undefined}
                      style={singleLine && column.width ? { width: column.width } : undefined}
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
                        className={column.numeric ? 'numeric' : undefined}
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
