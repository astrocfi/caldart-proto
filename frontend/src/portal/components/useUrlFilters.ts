/**
 * Filter values kept in the page's query string.
 *
 * Every list page keeps its filters in the URL, read and written through this
 * one hook, so a filtered view is a link that can be bookmarked or sent, and
 * the back button steps through the filters that were applied.
 */
import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';

import type { FilterValues } from '@/portal/reports/types';

/** The query parameter a paged list keeps its page number in. */
const PAGE_PARAM = 'page';

/** The keys back out of the comma-joined form the hooks' dependencies compare. */
function splitKeys(keyList: string): string[] {
  return keyList === '' ? [] : keyList.split(',');
}

/**
 * The filters named by `keys`, read from and written to the query string.
 *
 * The values hold every key, an absent parameter reading as `''`, and stay the
 * same object until the URL changes.  Setting them writes each key given a
 * non-empty value, removes every other key, and removes `page`, so a change of
 * filter always returns the list to its first page.  Parameters that are not
 * among `keys`, such as `ordering`, are kept; values for keys not among `keys`
 * are ignored.
 *
 * @param keys the query parameters that are this page's filters.
 * @returns the current values and a setter, like `useState`.
 */
export function useUrlFilters(
  keys: readonly string[],
): [FilterValues, (next: FilterValues) => void] {
  const [params, setParams] = useSearchParams();
  // Compared as one string, so a caller may pass a fresh array on every render.
  const keyList = keys.join(',');

  const values = useMemo(
    () => Object.fromEntries(splitKeys(keyList).map((key) => [key, params.get(key) ?? ''])),
    [keyList, params],
  );

  const setValues = useCallback(
    (next: FilterValues) => {
      setParams((current) => {
        const updated = new URLSearchParams(current);
        updated.delete(PAGE_PARAM);
        for (const key of splitKeys(keyList)) {
          const value = next[key] ?? '';
          if (value === '') updated.delete(key);
          else updated.set(key, value);
        }
        return updated;
      });
    },
    [keyList, setParams],
  );

  return [values, setValues];
}
