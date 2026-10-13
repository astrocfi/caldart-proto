import { useEffect, useRef } from 'react';
import type { RefObject } from 'react';

import { focusFirstField } from '@/portal/components/focus';

/**
 * Move the focus into `ref`'s first field, or its first button, each time `step`
 * changes after the first render, so a keyboard or screen reader user lands on the
 * step that just appeared rather than on the page body.
 */
export function useFocusOnChange(ref: RefObject<HTMLElement | null>, step: string): void {
  const previous = useRef(step);
  useEffect(() => {
    if (previous.current === step) return;
    previous.current = step;
    focusFirstField(ref.current);
  }, [ref, step]);
}
