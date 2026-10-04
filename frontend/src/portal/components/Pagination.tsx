/**
 * The portal's one pagination control, drawn by `DataTable` under a paged table.
 *
 * It reads "Showing 26–50 of 51" beside a **Previous** and a **Next** button, and
 * draws nothing while one page holds every row.  A button with nowhere to go is
 * disabled and drawn plainly so, with a dashed frame and muted words.
 */
import type { JSX } from 'react';

import { Button } from './Button';

/** What a paged table needs to draw its pagination control. */
export interface PaginationSettings {
  /** The page shown, a whole number from 1. */
  page: number;
  /** How many rows a page holds. */
  pageSize: number;
  /** How many rows there are in all, across every page. */
  count: number;
  /** Called with the page asked for. */
  onPageChange: (page: number) => void;
  /** The control's accessible name, such as "Member pages"; "Pages" unless given. */
  label?: string;
}

export interface PaginationProps extends PaginationSettings {
  /** Called after `onPageChange`, so the table can bring its first row into view. */
  onMoved?: () => void;
}

/** The number of the last page for `count` rows, `pageSize` to a page; at least 1. */
export function lastPageOf(count: number, pageSize: number): number {
  return Math.max(1, Math.ceil(count / pageSize));
}

/**
 * The words beside the buttons: the rows the page shows and the total, such as
 * "Showing 26–50 of 51".
 */
export function rangeText(page: number, pageSize: number, count: number): string {
  const first = count === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, count);
  return `Showing ${first}–${last} of ${count}`;
}

/**
 * Previous and Next with the range between them, or nothing when one page holds
 * every row.
 */
export function Pagination({
  page,
  pageSize,
  count,
  onPageChange,
  onMoved,
  label = 'Pages',
}: PaginationProps): JSX.Element | null {
  const lastPage = lastPageOf(count, pageSize);
  if (lastPage === 1 && page === 1) return null;

  const handleMove = (next: number): void => {
    onPageChange(next);
    onMoved?.();
  };

  return (
    <nav className="pagination" aria-label={label}>
      <Button variant="quiet" small disabled={page <= 1} onClick={() => handleMove(page - 1)}>
        Previous
      </Button>
      <span className="muted pagination__status" aria-live="polite">
        {rangeText(page, pageSize, count)}
      </span>
      <Button
        variant="quiet"
        small
        disabled={page >= lastPage}
        onClick={() => handleMove(page + 1)}
      >
        Next
      </Button>
    </nav>
  );
}
