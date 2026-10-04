/**
 * The keyboard behavior of a form that opens in a card on a list screen, such as
 * **New template** or a row's **Edit**: the focus moves into the form as it opens,
 * Escape closes it, and closing it puts the focus back on the control that opened it.
 */
import { useEffect, useRef } from 'react';
import type { RefObject } from 'react';

/** The fields the focus moves to as a form opens, the first of them in the page's order. */
const FIRST_FIELD = 'input, select, textarea, [contenteditable="true"]';

/** What counts as the control that opened a form. */
const CONTROL = 'a, button, input, select, textarea';

/**
 * Popovers inside a form that close on Escape themselves, so an Escape pressed in one
 * closes it and leaves the form open.
 */
const OWN_ESCAPE = '.panel-button__panel, .multi-select__panel';

/**
 * Keep the focus with the form named by `openKey`.
 *
 * @param openKey names the open form, such as `new` or `edit-3`, or null while none is
 *   open. A change from one form to another moves the focus into the new one.
 * @param onClose closes the form, on Escape.
 * @param fallbackRef takes the focus on close when the control that opened the form
 *   is no longer on the page, such as a row the form deleted.
 * @returns the ref for the element that holds the form.
 */
export function useFormCard(
  openKey: string | null,
  onClose: () => void,
  fallbackRef: RefObject<HTMLElement | null>,
): RefObject<HTMLDivElement | null> {
  const cardRef = useRef<HTMLDivElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const wasOpenRef = useRef(false);
  const closeRef = useRef(onClose);
  useEffect(() => {
    closeRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (openKey !== null) {
      if (!wasOpenRef.current) {
        // An opener that unmounted as the form opened, such as New template, has left
        // the focus on the page itself; the fallback stands in for it then.
        const active = document.activeElement;
        openerRef.current =
          active instanceof HTMLElement && active.matches(CONTROL) ? active : null;
      }
      wasOpenRef.current = true;
      cardRef.current?.querySelector<HTMLElement>(FIRST_FIELD)?.focus();
      return;
    }
    if (!wasOpenRef.current) return;
    wasOpenRef.current = false;
    const opener = openerRef.current;
    (opener !== null && opener.isConnected ? opener : fallbackRef.current)?.focus();
  }, [openKey, fallbackRef]);

  // A native listener on the card: a key pressed on any control inside bubbles to it.
  useEffect(() => {
    const card = cardRef.current;
    if (openKey === null || card === null) return undefined;
    const handleKeyDown = (event: KeyboardEvent): void => {
      if (event.key !== 'Escape' || event.defaultPrevented) return;
      if (event.target instanceof Element && event.target.closest(OWN_ESCAPE) !== null) return;
      event.preventDefault();
      closeRef.current();
    };
    card.addEventListener('keydown', handleKeyDown);
    return () => card.removeEventListener('keydown', handleKeyDown);
  }, [openKey]);

  return cardRef;
}
