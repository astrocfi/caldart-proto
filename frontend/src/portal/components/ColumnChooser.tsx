/**
 * The column chooser behind a report table and its two exports.
 *
 * The registry comes from the server, so the screen and the exports can never
 * offer different columns.  The chosen set always drives the CSV and the PDF; a
 * screen whose table follows it too says so in the panel's legend.
 */
import { useCallback, useRef, useState } from 'react';
import type { JSX } from 'react';

import type { ReportColumn } from '@/portal/api/types';
import { Button } from './Button';
import { useClickOutside } from './useClickOutside';

export interface ColumnChooserProps {
  /** Every column the exports can carry, in export order. */
  columns: ReportColumn[];
  /** The chosen keys, in registry order. */
  chosen: string[];
  onChange: (chosen: string[]) => void;
  /**
   * The panel's legend.  The default suits a screen whose table follows the
   * chosen columns; a screen whose table is fixed passes "Columns to export".
   */
  legend?: string;
}

/** The keys a fresh chooser starts with: the registry's own default columns. */
export function defaultColumnKeys(columns: ReportColumn[]): string[] {
  return columns.filter((column) => column.default).map((column) => column.key);
}

/**
 * The chosen keys with `key` added or removed, kept in registry order.
 *
 * Order matters: the export prints the columns in the order the registry lists
 * them, so the table has to agree however the boxes were ticked.  The last
 * column cannot be removed: an empty set would export the server's defaults
 * rather than what is on screen, and a table of nothing helps nobody.
 */
export function toggleColumn(columns: ReportColumn[], chosen: string[], key: string): string[] {
  const wanted = new Set(chosen);
  if (wanted.has(key)) {
    if (wanted.size === 1) return chosen;
    wanted.delete(key);
  } else wanted.add(key);
  return columns.filter((column) => wanted.has(column.key)).map((column) => column.key);
}

/**
 * The Columns button and the checkbox list it opens.
 *
 * The list closes on a click anywhere outside it and on Escape, so it never
 * sits over the table a treasurer is trying to read.  Closing it while the focus
 * is still inside puts the focus back on the Columns button, so a keyboard user
 * who presses Escape carries on from the control they opened rather than from
 * the top of the page.
 */
export function ColumnChooser({
  columns,
  chosen,
  onChange,
  legend = 'Columns to show and export',
}: ColumnChooserProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const handleClose = useCallback(() => {
    setIsOpen(false);
    // The panel is about to unmount.  If the focus is inside it, it would fall to
    // the document body, so hand it back to the button that opened the panel.  A
    // pointer press outside then moves it on to whatever was pressed.
    const root = rootRef.current;
    if (root !== null && root.contains(document.activeElement)) {
      root.querySelector<HTMLButtonElement>('.column-chooser__toggle')?.focus();
    }
  }, []);

  useClickOutside(rootRef, handleClose, isOpen);

  function handleToggle(key: string) {
    onChange(toggleColumn(columns, chosen, key));
  }

  return (
    <div className="column-chooser" ref={rootRef}>
      <Button
        variant="quiet"
        small
        className="column-chooser__toggle"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
      >
        Columns
      </Button>
      {isOpen ? (
        <fieldset className="column-chooser__panel">
          <legend>{legend}</legend>
          {columns.map((column) => (
            <label key={column.key} className="column-chooser__option">
              <input
                type="checkbox"
                checked={chosen.includes(column.key)}
                disabled={chosen.length === 1 && chosen.includes(column.key)}
                onChange={() => handleToggle(column.key)}
              />
              {column.label}
            </label>
          ))}
          <Button variant="quiet" small onClick={() => onChange(defaultColumnKeys(columns))}>
            Reset to the default columns
          </Button>
        </fieldset>
      ) : null}
    </div>
  );
}
