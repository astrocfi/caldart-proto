/**
 * The order and the page of a server-paged list, kept in the query string.
 *
 * A list page keeps its filters in the address through `useUrlFilters`; this
 * keeps the `ordering` and `page` parameters beside them, each through its own
 * `useUrlFilters`, so a change of filter or of order returns the list to its
 * first page, and a sorted, paged view can be linked.
 */
import { useCallback, useEffect } from 'react';

import { ApiError } from '@/portal/api/client';
import type { SortDirection } from './DataTable';
import { useUrlFilters } from './useUrlFilters';

const ORDERING_KEYS = ['ordering'];
const PAGE_KEYS = ['page'];

/** The column and direction a table shows as sorted. */
export interface TableSort {
  key: string;
  direction: SortDirection;
}

/** A list's order and page, read from the address, and their setters. */
export interface UrlListPosition {
  /** The `ordering` term the list is asked for. */
  ordering: string;
  /** The same order as the column and direction `DataTable` draws. */
  sort: TableSort;
  /** The page asked for, a whole number from 1. */
  page: number;
  /** Order by a column, as `DataTable`'s `onSortChange` reports it. */
  setSort: (key: string, direction: SortDirection) => void;
  /** Go to a page; page 1 leaves the parameter out of the address. */
  setPage: (page: number) => void;
}

/**
 * The API `ordering` term for a column and direction.
 *
 * @param key the column's key, which is its `ordering` field.
 * @param direction ascending or descending.
 * @returns `key`, prefixed with `-` when descending.
 */
export function orderingFor(key: string, direction: SortDirection): string {
  return direction === 'desc' ? `-${key}` : key;
}

/**
 * The column and direction an `ordering` term sorts by.
 *
 * @param ordering an API ordering term such as `-paid_at`.
 * @returns the field without its sign, and `desc` when it carried one.
 */
export function sortFor(ordering: string): TableSort {
  return ordering.startsWith('-')
    ? { key: ordering.slice(1), direction: 'desc' }
    : { key: ordering, direction: 'asc' };
}

/**
 * The page a `page` parameter names.
 *
 * @param value the parameter as the address holds it, `''` when absent.
 * @returns the number when it is a whole number of at least 1, else 1.
 */
export function pageFrom(value: string): number {
  const page = Number(value);
  return Number.isInteger(page) && page >= 1 ? page : 1;
}

/**
 * The list's order and page, read from and written to the query string.
 *
 * @param defaultOrdering the order used while the address names none.
 * @returns the order, the page and their setters.
 */
export function useUrlListPosition(defaultOrdering: string): UrlListPosition {
  const [orderingValues, setOrderingValues] = useUrlFilters(ORDERING_KEYS);
  const [pageValues, setPageValues] = useUrlFilters(PAGE_KEYS);

  const ordering = orderingValues.ordering || defaultOrdering;

  const setSort = useCallback(
    (key: string, direction: SortDirection) =>
      setOrderingValues({ ordering: orderingFor(key, direction) }),
    [setOrderingValues],
  );
  const setPage = useCallback(
    (page: number) => setPageValues({ page: page > 1 ? String(page) : '' }),
    [setPageValues],
  );

  return {
    ordering,
    sort: sortFor(ordering),
    page: pageFrom(pageValues.page ?? ''),
    setSort,
    setPage,
  };
}

/**
 * Return to the first page when the list answers that the page asked for does
 * not exist, as a bookmarked page does once the list has shrunk below it.
 *
 * @param position the list's position, from `useUrlListPosition`.
 * @param error the list query's error, or null.
 */
export function useFirstPageWhenMissing(position: UrlListPosition, error: unknown): void {
  const { page, setPage } = position;
  const isMissing = page > 1 && error instanceof ApiError && error.status === 404;
  useEffect(() => {
    if (isMissing) setPage(1);
  }, [isMissing, setPage]);
}
