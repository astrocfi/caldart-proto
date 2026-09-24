/**
 * Dismiss a popover the way a person expects: click away, or press Escape.
 *
 * The listeners sit on the document and only while the popover is open, so a
 * shut popover costs nothing and two open ones cannot fight over an event.
 * `pointerdown` rather than `click`, so the popover is gone before whatever was
 * clicked underneath reacts.
 */
import { useEffect } from 'react';
import type { RefObject } from 'react';

/**
 * Call `onOutside` while `isActive` for a pointer press outside `ref.current`
 * and for the Escape key, wherever the focus lies.
 *
 * A press inside the referenced element, any other key, and every event while
 * `isActive` is false are ignored, as is everything after the caller unmounts.
 */
export function useClickOutside(
  ref: RefObject<HTMLElement | null>,
  onOutside: () => void,
  isActive: boolean,
): void {
  useEffect(() => {
    if (!isActive) return;

    const handlePointerDown = (event: PointerEvent | MouseEvent): void => {
      const target = event.target;
      if (target instanceof Node && ref.current?.contains(target) === true) return;
      onOutside();
    };
    const handleKeyDown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') onOutside();
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [ref, onOutside, isActive]);
}
