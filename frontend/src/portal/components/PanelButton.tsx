/**
 * A button that opens a small panel under itself, the way the column chooser's
 * three buttons do.
 *
 * The panel closes on a click anywhere outside it, on Escape, and when the focus
 * moves on past it to another control (Tab from its last control, say), so it never
 * sits over the table somebody is trying to read, or over a control the focus has
 * moved to.  A press anywhere inside it leaves it open.  Closing it while the focus is
 * still inside puts the focus back on the button, so a keyboard user carries on
 * from the control they opened rather than from the top of the page.
 *
 * The panel opens under its button and is moved sideways, if need be, so that it stays
 * on the screen, as when a phone wraps a row of buttons and the button sits near an
 * edge.
 *
 * A panel of choices, such as a list of columns, keeps to a fixed height and
 * scrolls; a panel that holds a form (`isForm`) takes the height its form needs, so
 * the button that sends it is never cut off.
 */
import { useCallback, useId, useLayoutEffect, useRef, useState } from 'react';
import type { FocusEvent, JSX, ReactNode } from 'react';

import { Button } from './Button';
import { useClickOutside } from './useClickOutside';

/** The least gap kept between an open panel and either side of the screen, in pixels. */
const SCREEN_MARGIN_PX = 8;

/**
 * How far to move a panel sideways so that it lies within the screen: left when it
 * runs past the right edge, right when it starts before the left edge.
 *
 * @param left the panel's left edge, in pixels from the screen's left.
 * @param right the panel's right edge.
 * @param screenWidth the width of the screen, less any scroll bar.
 * @returns the shift in pixels, negative to move left, 0 when it already fits.
 */
export function panelShift(left: number, right: number, screenWidth: number): number {
  let shift = 0;
  if (right > screenWidth - SCREEN_MARGIN_PX) shift = screenWidth - SCREEN_MARGIN_PX - right;
  if (left + shift < SCREEN_MARGIN_PX) shift = SCREEN_MARGIN_PX - left;
  return shift;
}

export interface PanelButtonProps {
  /** The button's words, which are also its accessible name unless `name` is given. */
  label: string;
  /** The accessible name, when the words alone do not say which of two buttons it is. */
  name?: string;
  /** The panel's caption, which names it as a group. */
  legend: string;
  /**
   * The panel's contents, drawn only while it is open.  They receive a function
   * that closes the panel, for a choice that finishes the panel's work.
   */
  children: (handleClose: () => void) => ReactNode;
  /** The panel holds a form: it grows to the form's height rather than scrolling. */
  isForm?: boolean;
}

/**
 * A quiet small `Button` with `aria-expanded` and `aria-controls`, and the
 * captioned panel it opens and shuts.
 *
 * The panel's contents mount only while it is open, so anything they fetch is
 * fetched only once somebody asks for the panel.
 */
export function PanelButton({
  label,
  name,
  legend,
  children,
  isForm = false,
}: PanelButtonProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLFieldSetElement>(null);
  const [shift, setShift] = useState(0);

  // Measured before the panel paints, so it never shows cut off at a screen edge.
  useLayoutEffect(() => {
    const panel = panelRef.current;
    if (!isOpen || panel === null) {
      setShift(0);
      return;
    }
    const { left, right } = panel.getBoundingClientRect();
    setShift(panelShift(left, right, document.documentElement.clientWidth));
  }, [isOpen]);

  const handleClose = useCallback(() => {
    setIsOpen(false);
    // The panel is about to unmount.  If the focus is inside it, it would fall to
    // the document body, so hand it back to the button that opened the panel.  A
    // pointer press outside then moves it on to whatever was pressed.
    const root = rootRef.current;
    if (root !== null && root.contains(document.activeElement)) {
      root.querySelector<HTMLButtonElement>(':scope > .panel-button__toggle')?.focus();
    }
  }, []);

  useClickOutside(rootRef, handleClose, isOpen);

  // Focus that moves to a control outside shuts the panel without pulling the focus
  // back; focus that goes nowhere, as when a control in the panel unmounts, leaves it.
  // So does focus that moves to a region holding the panel, such as the portal's
  // focusable `<main>`, which takes it on a press on plain words or a label inside
  // the panel: closing then would swallow the press, and the label's radio button
  // would never be checked.
  const handleBlur = (event: FocusEvent<HTMLDivElement>): void => {
    const next = event.relatedTarget;
    const root = event.currentTarget;
    if (next instanceof Node && !root.contains(next) && !next.contains(root)) setIsOpen(false);
  };

  return (
    <div className="panel-button" ref={rootRef} onBlur={handleBlur}>
      <Button
        variant="quiet"
        small
        className="panel-button__toggle"
        onClick={() => setIsOpen((open) => !open)}
        aria-label={name}
        aria-expanded={isOpen}
        aria-controls={isOpen ? panelId : undefined}
      >
        {label}
      </Button>
      {isOpen ? (
        <fieldset
          ref={panelRef}
          id={panelId}
          style={shift === 0 ? undefined : { transform: `translateX(${shift}px)` }}
          className={
            isForm ? 'panel-button__panel panel-button__panel--form' : 'panel-button__panel'
          }
        >
          <legend>{legend}</legend>
          {children(handleClose)}
        </fieldset>
      ) : null}
    </div>
  );
}
