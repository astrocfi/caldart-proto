/**
 * A drop-down that takes several choices.
 *
 * The shut box is one line, like a select: the chosen labels in the order the
 * options list them, or the placeholder while nothing is chosen.  Pressing it
 * opens a panel of checkboxes under it.  Each checkbox applies as it is ticked or
 * unticked, so any choice, the last one included, can be taken back on its own,
 * and **Clear** takes them all back at once.  The panel shuts on a click outside
 * it and on Escape, handing the focus back to the box.  A screen reader hears the
 * box by its legend and what it holds, *County: Any*, not by what it holds alone.
 */
import { useCallback, useId, useRef, useState } from 'react';
import type { JSX } from 'react';

import type { Option } from '@/portal/reports/types';
import { Button } from './Button';
import { useClickOutside } from './useClickOutside';

export interface MultiSelectProps {
  /** The box's `id`, which a `Field`'s label points at. */
  id: string;
  /** The panel's caption, which names the group of checkboxes to a screen reader. */
  legend: string;
  options: readonly Option[];
  /** The chosen values. */
  value: readonly string[];
  /** Called with the chosen values, in the order `options` lists them. */
  onChange: (value: string[]) => void;
  /** What the shut box says while nothing is chosen; `Any` unless given. */
  placeholder?: string;
  title?: string;
  'aria-describedby'?: string;
}

/** The chosen options' labels, in list order, joined for the shut box. */
function summarize(options: readonly Option[], value: readonly string[]): string {
  const chosen = new Set(value);
  return options
    .filter((option) => chosen.has(option.value))
    .map((option) => option.label)
    .join(', ');
}

/**
 * A button that reads as the chosen options and opens a panel of checkboxes,
 * one per option, with **Clear** beneath them.
 */
export function MultiSelect({
  id,
  legend,
  options,
  value,
  onChange,
  placeholder = 'Any',
  title,
  'aria-describedby': describedBy,
}: MultiSelectProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  const handleClose = useCallback(() => {
    setIsOpen(false);
    // The panel is about to unmount.  If the focus is inside it, it would fall to
    // the document body, so hand it back to the box that opened the panel.
    const root = rootRef.current;
    if (root !== null && root.contains(document.activeElement)) {
      root.querySelector<HTMLButtonElement>(':scope > .multi-select__toggle')?.focus();
    }
  }, []);

  useClickOutside(rootRef, handleClose, isOpen);

  const handleToggle = (toggled: string): void => {
    const chosen = new Set(value);
    if (chosen.has(toggled)) chosen.delete(toggled);
    else chosen.add(toggled);
    onChange(options.filter((option) => chosen.has(option.value)).map((option) => option.value));
  };

  const summary = summarize(options, value);
  const shown = summary === '' ? placeholder : summary;

  return (
    <div className="multi-select" ref={rootRef}>
      <button
        type="button"
        id={id}
        className="multi-select__toggle"
        aria-label={`${legend}: ${shown}`}
        title={title}
        aria-describedby={describedBy}
        aria-expanded={isOpen}
        aria-controls={isOpen ? panelId : undefined}
        onClick={() => setIsOpen((open) => !open)}
      >
        <span className={summary === '' ? 'multi-select__placeholder' : undefined}>{shown}</span>
        <span className="multi-select__caret" aria-hidden="true" />
      </button>
      {isOpen ? (
        <fieldset id={panelId} className="multi-select__panel">
          <legend className="visually-hidden">{legend}</legend>
          {options.map((option) => (
            <label key={option.value} className="multi-select__option">
              <input
                type="checkbox"
                value={option.value}
                checked={value.includes(option.value)}
                onChange={() => handleToggle(option.value)}
              />
              {option.label}
            </label>
          ))}
          <Button variant="quiet" small disabled={value.length === 0} onClick={() => onChange([])}>
            Clear
          </Button>
        </fieldset>
      ) : null}
    </div>
  );
}
