/**
 * The column chooser behind the payments table and its two exports.
 *
 * The registry comes from the server, so the screen and the exports can never
 * offer different columns, and the chosen set drives both at once: what is on
 * screen is what the CSV and the PDF will carry.
 */
import { useState } from 'react';
import type { JSX } from 'react';

import type { ReportColumn } from '@/portal/api/types';
import { Button } from '@/portal/components/Button';

export interface ColumnChooserProps {
  /** Every column the exports can carry, in export order. */
  columns: ReportColumn[];
  /** The chosen keys, in registry order. */
  chosen: string[];
  onChange: (chosen: string[]) => void;
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

/** The Columns button and the checkbox list it opens. */
export function ColumnChooser({ columns, chosen, onChange }: ColumnChooserProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);

  function handleToggle(key: string) {
    onChange(toggleColumn(columns, chosen, key));
  }

  return (
    <div className="column-chooser">
      <Button
        variant="quiet"
        small
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
      >
        Columns
      </Button>
      {isOpen ? (
        <fieldset className="column-chooser__panel">
          <legend>Columns to show and export</legend>
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
