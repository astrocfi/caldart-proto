/**
 * Whether a table's scroll box is wider inside than out, and which way it can scroll.
 *
 * `DataTable` reads this to show its scroll cue, to make the box a focusable,
 * named region a keyboard can scroll, and to pin its identifying column while the
 * table scrolls.  The box is measured again when it or the table inside it changes
 * size, and as it scrolls.
 */
import { useLayoutEffect, useState } from 'react';
import type { RefObject } from 'react';

/** How a scroll box sits: whether it scrolls at all, and whether more lies either side. */
export interface TableScroll {
  isOverflowing: boolean;
  /** More of the table lies to the left of what shows. */
  hasMoreLeft: boolean;
  /** More of the table lies to the right of what shows. */
  hasMoreRight: boolean;
}

const AT_REST: TableScroll = { isOverflowing: false, hasMoreLeft: false, hasMoreRight: false };

/** Sub-pixel layouts leave a fraction of a pixel over; anything less is no overflow. */
const SLACK_PX = 1;

/** How `box` sits now. */
function measure(box: HTMLElement): TableScroll {
  const overflow = box.scrollWidth - box.clientWidth;
  if (overflow <= SLACK_PX) return AT_REST;
  return {
    isOverflowing: true,
    hasMoreLeft: box.scrollLeft > SLACK_PX,
    hasMoreRight: box.scrollLeft < overflow - SLACK_PX,
  };
}

/** Whether two readings say the same, so an unchanged reading does not re-render. */
function same(a: TableScroll, b: TableScroll): boolean {
  return (
    a.isOverflowing === b.isOverflowing &&
    a.hasMoreLeft === b.hasMoreLeft &&
    a.hasMoreRight === b.hasMoreRight
  );
}

/**
 * How the scroll box `ref` holds sits, kept up to date.
 *
 * @param ref the scroll box; nothing is measured while it is unmounted.
 * @param isMounted whether the box is drawn now, so the hook measures it again when
 *   it appears, such as after an empty state gives way to rows.
 * @returns whether it overflows and which way more of the table lies.
 */
export function useTableScroll(
  ref: RefObject<HTMLElement | null>,
  isMounted: boolean,
): TableScroll {
  const [scroll, setScroll] = useState<TableScroll>(AT_REST);
  useLayoutEffect(() => {
    const box = ref.current;
    if (box === null || !isMounted) {
      setScroll(AT_REST);
      return undefined;
    }
    const update = (): void => {
      const next = measure(box);
      setScroll((current) => (same(current, next) ? current : next));
    };
    update();
    box.addEventListener('scroll', update, { passive: true });
    if (typeof ResizeObserver === 'undefined') {
      return () => box.removeEventListener('scroll', update);
    }
    const observer = new ResizeObserver(update);
    observer.observe(box);
    if (box.firstElementChild !== null) observer.observe(box.firstElementChild);
    return () => {
      box.removeEventListener('scroll', update);
      observer.disconnect();
    };
  }, [ref, isMounted]);
  return scroll;
}
