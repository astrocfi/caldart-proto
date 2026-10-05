/**
 * Where the keyboard focus goes as the portal's panels open and close, and after a
 * submit the form refuses.
 *
 * A screen reader user or a keyboard user follows the focus, so every action that
 * opens, closes, or refuses something says where the focus lands next rather than
 * leaving it on the page body, from where the next Tab starts again at the header.
 *
 * - `usePanelFocus` is for a panel or form that opens in place, such as **New
 *   template**, a row's **Edit**, or a member's **Change**: the focus moves into the
 *   panel as it opens, Escape closes it, and closing it puts the focus back on the
 *   control that opened it.
 * - `focusRefusal` moves the focus to the first highlighted field of a refused form,
 *   or to the form's own complaint when no field is highlighted.
 * - `useFocusAfterSave` puts the focus back on a button, or a form's submit button,
 *   or a switch, after a request that leaves it in place, which it lost while disabled.
 * - `useFocusRunResult` moves the focus to what a run did, once the run ends, so a
 *   keyboard or screen reader user lands on the result rather than on the button.
 */
import { useEffect, useRef } from 'react';
import type { RefObject } from 'react';

/** The fields the focus moves to as a panel opens, the first of them in the page's order. */
const FIRST_FIELD = 'input, select, textarea, [contenteditable="true"]';

/** A button the focus may land on in a panel that holds no field, such as a confirmation. */
const FIRST_BUTTON = 'button:not([disabled]), a[href]';

/** What counts as the control that opened a panel. */
const CONTROL = 'a, button, input, select, textarea';

/**
 * Popovers and confirmations inside a panel that close on Escape themselves, so an
 * Escape pressed in one closes it and leaves the panel open.  `data-own-escape` marks
 * the confirmation panels of `ConfirmButton` and `DeleteButton`; `aria-expanded="true"`
 * marks the control of an open popover, such as a `Typeahead` box with its list showing
 * or the toggle of an open `MultiSelect` or `PanelButton`, where the focus sits while
 * the popover is open.  The panel's own listener hears the key before the popover's
 * document listener does, so it has to recognize the popover rather than wait for it.
 */
const OWN_ESCAPE =
  '.panel-button__panel, .multi-select__panel, [data-own-escape], [aria-expanded="true"]';

/** A field the form has marked as wrong, by `Field` or by hand. */
const INVALID_FIELD = '[aria-invalid="true"]';

/** A form's own complaint, such as a `FormAlert`, when no field carries the error. */
const FORM_COMPLAINT = '[role="alert"]';

/** The submit button of a form, which keeps the focus after a save. */
const SUBMIT_BUTTON = 'button[type="submit"]';

/**
 * Focus `element` and bring it to the middle of the screen, so the label above a
 * field and the message under it are in view too, not just the box's own edge.
 */
export function focusIntoView(element: HTMLElement): void {
  element.focus({ preventScroll: true });
  // jsdom has no layout, and so no `scrollIntoView`.
  if (typeof element.scrollIntoView === 'function') {
    element.scrollIntoView({ block: 'center' });
  }
}

/**
 * Focus the first field in `root`; failing a field, its first enabled button or link;
 * failing that, `root` itself, made focusable for the purpose.
 *
 * Does nothing when `root` is null.
 */
export function focusFirstField(root: HTMLElement | null): void {
  if (root === null) return;
  const target =
    root.querySelector<HTMLElement>(FIRST_FIELD) ?? root.querySelector<HTMLElement>(FIRST_BUTTON);
  if (target !== null) {
    focusIntoView(target);
    return;
  }
  root.tabIndex = -1;
  focusIntoView(root);
}

/** How many fields in `root` are marked invalid; 0 when `root` is null. */
export function countInvalidFields(root: HTMLElement | null): number {
  return root === null ? 0 : root.querySelectorAll(INVALID_FIELD).length;
}

/**
 * Move the focus to what a refused submit wants the person to fix.
 *
 * That is the first field in `root` marked `aria-invalid="true"`; when no field is
 * marked, it is the first `role="alert"` message in `root`, made focusable for the
 * purpose; when there is neither, the focus stays where it is.  Either way the target
 * is scrolled to the middle of the screen, so a person who pressed a button at the
 * foot of a long form sees what went wrong.
 *
 * @returns how many fields are marked invalid.
 */
export function focusRefusal(root: HTMLElement | null): number {
  if (root === null) return 0;
  const invalid = root.querySelector<HTMLElement>(INVALID_FIELD);
  if (invalid !== null) {
    focusIntoView(invalid);
    return countInvalidFields(root);
  }
  const complaint = root.querySelector<HTMLElement>(FORM_COMPLAINT);
  if (complaint !== null) {
    complaint.tabIndex = -1;
    focusIntoView(complaint);
  }
  return 0;
}

/** Whether the focus has been lost: it sits on the page itself, or on nothing. */
function isFocusLost(): boolean {
  const active = document.activeElement;
  return active === null || active === document.body || !active.isConnected;
}

/**
 * Keep the focus with the panel named by `openKey`.
 *
 * As the panel opens the focus moves to its first field (or, in a panel without
 * fields, its first button).  An Escape pressed anywhere inside it calls `onClose`,
 * unless it was pressed in an open popover or confirmation inside the panel, which
 * closes that alone.  As it
 * closes, the focus goes back to the control that had it when the panel opened, or to
 * `fallbackRef` when that control is no longer on the page, such as an **Edit** button
 * the panel replaced or a row the panel deleted.
 *
 * @param openKey names the open panel, such as `new` or `edit-3`, or null while none is
 *   open. A change from one panel to another moves the focus into the new one.
 * @param onClose closes the panel, on Escape.
 * @param fallbackRef takes the focus on close when the opener is gone.
 * @returns the ref for the element that holds the panel.
 */
export function usePanelFocus<Panel extends HTMLElement = HTMLDivElement>(
  openKey: string | null,
  onClose: () => void,
  fallbackRef?: RefObject<HTMLElement | null>,
): RefObject<Panel | null> {
  const panelRef = useRef<Panel>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const wasOpenRef = useRef(false);
  const closeRef = useRef(onClose);
  useEffect(() => {
    closeRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (openKey !== null) {
      if (!wasOpenRef.current) {
        // An opener that unmounted as the panel opened, such as an Edit button the
        // form took the place of, has left the focus on the page itself; the
        // fallback stands in for it then.
        const active = document.activeElement;
        openerRef.current =
          active instanceof HTMLElement && active.matches(CONTROL) ? active : null;
      }
      wasOpenRef.current = true;
      focusFirstField(panelRef.current);
      return;
    }
    if (!wasOpenRef.current) return;
    wasOpenRef.current = false;
    const opener = openerRef.current;
    (opener !== null && opener.isConnected ? opener : (fallbackRef?.current ?? null))?.focus();
  }, [openKey, fallbackRef]);

  // A native listener on the panel: a key pressed on any control inside bubbles to it.
  useEffect(() => {
    const panel = panelRef.current;
    if (openKey === null || panel === null) return undefined;
    const handleKeyDown = (event: KeyboardEvent): void => {
      if (event.key !== 'Escape' || event.defaultPrevented) return;
      // A popover inside the panel takes the key; one around the panel does not count.
      const owner = event.target instanceof Element ? event.target.closest(OWN_ESCAPE) : null;
      if (owner !== null && owner !== panel && panel.contains(owner)) return;
      event.preventDefault();
      closeRef.current();
    };
    panel.addEventListener('keydown', handleKeyDown);
    return () => panel.removeEventListener('keydown', handleKeyDown);
  }, [openKey]);

  return panelRef;
}

/**
 * Put the focus back on a control once `isPending` ends, when it has nowhere better to be.
 *
 * `ref` is the control itself, such as a button or a switch, or a form whose submit
 * button is meant.  A button is
 * disabled while its request is in flight, and a disabled button drops the focus to the
 * page body.  When the request ends and the focus is still lost, it returns to the
 * button, so the person carries on from where they pressed; a refusal that has already
 * moved it to a highlighted field keeps it there.
 */
export function useFocusAfterSave(ref: RefObject<HTMLElement | null>, isPending: boolean): void {
  const wasPendingRef = useRef(false);
  useEffect(() => {
    const wasPending = wasPendingRef.current;
    wasPendingRef.current = isPending;
    if (!wasPending || isPending || !isFocusLost()) return;
    const root = ref.current;
    const control =
      root?.matches('form') === true ? root.querySelector<HTMLElement>(SUBMIT_BUTTON) : root;
    control?.focus();
  }, [ref, isPending]);
}

/** What takes the focus in a run's result: its heading, or failing that its message. */
const RESULT_TARGET = 'h3, h4, [role="alert"], [role="status"]';

/**
 * Move the focus to a run's result as the run ends.
 *
 * @returns a ref for the element the result is drawn in. When `isRunning` turns false,
 *   or a result appears where there was none (a run so quick it never drew as running),
 *   the focus moves to the result's heading or, failing that, its alert or status line,
 *   made focusable (`tabindex="-1"`) for the purpose and brought into view.  Nothing
 *   moves when the result holds none of them.
 */
export function useFocusRunResult<Result extends HTMLElement = HTMLDivElement>(
  isRunning: boolean,
): RefObject<Result | null> {
  const resultRef = useRef<Result>(null);
  const wasRunningRef = useRef(false);
  // `undefined` until the first render has been seen: whatever result the page opens
  // with is not news, and never takes the focus.
  const lastTargetRef = useRef<HTMLElement | null | undefined>(undefined);
  useEffect(() => {
    const wasRunning = wasRunningRef.current;
    wasRunningRef.current = isRunning;
    if (isRunning) return;
    const target = resultRef.current?.querySelector<HTMLElement>(RESULT_TARGET) ?? null;
    const isFresh = lastTargetRef.current !== undefined && target !== lastTargetRef.current;
    lastTargetRef.current = target;
    if (target === null || !(wasRunning || isFresh)) return;
    target.tabIndex = -1;
    focusIntoView(target);
  });
  return resultRef;
}

/** The places around a control the focus may fall back to, nearest first. */
const NEAR_PLACES = 'td, th, li';

/** The heading of the card or section a control sits in. */
const CARD_HEADING = ':scope > h2, :scope > h3, :scope > .card__title';

/**
 * Remember where `control` sits, for the moment after an action that may take it away.
 *
 * @returns a function that, when called later, gives `control` itself while it is
 *   still on the page and enabled; failing that, the table cell or list item it sat in
 *   while that is still on the page; failing that, the heading of the card or section
 *   around it. A cell, item, or heading is made focusable (`tabindex="-1"`) for the
 *   purpose. It gives null when none of them is left, or when `control` was null.
 */
export function rememberPlace(control: HTMLElement | null): () => HTMLElement | null {
  const near = control?.closest<HTMLElement>(NEAR_PLACES) ?? null;
  const section = control?.closest<HTMLElement>('section, .card') ?? null;
  return () => {
    if (control === null) return null;
    if (control.isConnected && !control.matches(':disabled')) return control;
    const heading = section?.isConnected ? section.querySelector<HTMLElement>(CARD_HEADING) : null;
    const place = near?.isConnected ? near : heading;
    if (place === null) return null;
    place.tabIndex = -1;
    return place;
  };
}

/**
 * When the component unmounts after an action armed it, hand a lost focus to the place
 * `placeRef` remembers.
 *
 * An action such as a delete can take its own control away with the row it sat in;
 * the control is then gone before it could put the focus anywhere.  Arm `armedRef`
 * as the action settles, and if that unmounts the component while the focus is on
 * the page body, the focus goes to `placeRef.current()` (see `rememberPlace`).
 */
export function useRefocusOnUnmount(
  placeRef: RefObject<(() => HTMLElement | null) | null>,
  armedRef: RefObject<boolean>,
): void {
  useEffect(
    () => () => {
      if (armedRef.current && isFocusLost()) placeRef.current?.()?.focus();
    },
    [placeRef, armedRef],
  );
}
