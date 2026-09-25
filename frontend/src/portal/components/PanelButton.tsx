/**
 * A button that opens a small panel under itself, the way the column chooser's
 * three buttons do.
 *
 * The panel closes on a click anywhere outside it and on Escape, so it never
 * sits over the table somebody is trying to read.  Closing it while the focus is
 * still inside puts the focus back on the button, so a keyboard user carries on
 * from the control they opened rather than from the top of the page.
 */
import { useCallback, useId, useRef, useState } from 'react';
import type { JSX, ReactNode } from 'react';

import { Button } from './Button';
import { useClickOutside } from './useClickOutside';

export interface PanelButtonProps {
  /** The button's words, which are also its accessible name. */
  label: string;
  /** The panel's caption, which names it as a group. */
  legend: string;
  /**
   * The panel's contents, drawn only while it is open.  They receive a function
   * that closes the panel, for a choice that finishes the panel's work.
   */
  children: (handleClose: () => void) => ReactNode;
}

/**
 * A quiet small `Button` with `aria-expanded` and `aria-controls`, and the
 * captioned panel it opens and shuts.
 *
 * The panel's contents mount only while it is open, so anything they fetch is
 * fetched only once somebody asks for the panel.
 */
export function PanelButton({ label, legend, children }: PanelButtonProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

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

  return (
    <div className="panel-button" ref={rootRef}>
      <Button
        variant="quiet"
        small
        className="panel-button__toggle"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
        aria-controls={isOpen ? panelId : undefined}
      >
        {label}
      </Button>
      {isOpen ? (
        <fieldset id={panelId} className="panel-button__panel">
          <legend>{legend}</legend>
          {children(handleClose)}
        </fieldset>
      ) : null}
    </div>
  );
}
