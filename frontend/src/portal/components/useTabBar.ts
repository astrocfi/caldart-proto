/**
 * What a tab bar too wide for its screen needs: to scroll sideways on one line, with
 * the current tab in view and a fade at each edge that hides more tabs.
 *
 * `FinanceTabs` and the member record's tabs spread the returned attributes on their
 * `.tab-bar`; the CSS reads `data-more-left` and `data-more-right` for the fades.
 */
import { useLayoutEffect, useRef } from 'react';
import type { RefObject } from 'react';

import { useTableScroll } from './useTableScroll';

/** The attributes a tab bar carries for its edge fades. */
export interface TabBarAttributes {
  'data-more-left': 'true' | 'false';
  'data-more-right': 'true' | 'false';
}

/**
 * Keep the tab bar in `ref` scrolled so its current tab (`aria-current="page"` or
 * `aria-selected="true"`) shows, whenever `current` changes, and say which edges hide
 * more tabs.  The bar scrolls by itself, never the page.
 *
 * @param current the current tab's key, read only to know when it changes.
 * @returns the ref for the bar and the attributes that drive its fades.
 */
export function useTabBar<Bar extends HTMLElement>(
  current: string,
): { ref: RefObject<Bar | null>; attributes: TabBarAttributes } {
  const ref = useRef<Bar | null>(null);
  const scroll = useTableScroll(ref, true);

  useLayoutEffect(() => {
    const bar = ref.current;
    const tab = bar?.querySelector<HTMLElement>('[aria-current="page"], [aria-selected="true"]');
    if (bar === null || tab === null || tab === undefined) return;
    const left = tab.offsetLeft - bar.offsetLeft;
    const right = left + tab.offsetWidth;
    if (left < bar.scrollLeft) bar.scrollLeft = left;
    else if (right > bar.scrollLeft + bar.clientWidth) bar.scrollLeft = right - bar.clientWidth;
  }, [current]);

  return {
    ref,
    attributes: {
      'data-more-left': scroll.hasMoreLeft ? 'true' : 'false',
      'data-more-right': scroll.hasMoreRight ? 'true' : 'false',
    },
  };
}
