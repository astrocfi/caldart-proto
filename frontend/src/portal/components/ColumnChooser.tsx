/**
 * The column chooser behind a report table and its two exports.
 *
 * The registry comes from the server, so the screen and the exports can never
 * offer different columns.  The chosen set always drives the CSV and the PDF; a
 * screen whose table follows it too says so in the panel's legend.  Under the
 * boxes, each user keeps named sets of a report's columns: load one and keep
 * editing, or save the boxes as they stand under a name.
 */
import { useCallback, useId, useRef, useState } from 'react';
import type { ChangeEvent, JSX, KeyboardEvent } from 'react';

import type { ReportColumn } from '@/portal/api/types';
import { useColumnSets, useDeleteColumnSet, useSaveColumnSet } from '@/portal/reports/api';
import type { ReportSlug } from '@/portal/reports/types';
import { Button } from './Button';
import { IconButton } from './IconButton';
import { useClickOutside } from './useClickOutside';

/** The longest name the server keeps for a saved set of columns. */
const MAX_SET_NAME = 60;

export interface ColumnChooserProps {
  /** The report whose columns these are, which also names the saved sets to offer. */
  report: ReportSlug;
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
 * A saved set's columns as the chooser holds them: in registry order, without
 * any key the registry no longer carries.
 *
 * A set that has lost every one of its keys yields the registry's defaults,
 * since the chooser never holds an empty choice.
 */
export function columnsOfSet(columns: ReportColumn[], saved: readonly string[]): string[] {
  const wanted = new Set(saved);
  const kept = columns.filter((column) => wanted.has(column.key)).map((column) => column.key);
  return kept.length > 0 ? kept : defaultColumnKeys(columns);
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
  report,
  columns,
  chosen,
  onChange,
  legend = 'Columns to show and export',
}: ColumnChooserProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  // Which saved set is selected, and the name box, outlive the panel, so a set
  // loaded before the chooser was put away is still the one selected on reopening.
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [name, setName] = useState('');
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
          <SavedColumnSets
            report={report}
            columns={columns}
            chosen={chosen}
            onChange={(next) => onChange(next)}
            selectedId={selectedId}
            onSelect={(id) => setSelectedId(id)}
            name={name}
            onNameChange={(next) => setName(next)}
          />
        </fieldset>
      ) : null}
    </div>
  );
}

interface SavedColumnSetsProps {
  report: ReportSlug;
  columns: ReportColumn[];
  chosen: string[];
  onChange: (chosen: string[]) => void;
  /** The saved set on show in the drop-down, or null for none. */
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  /** What the name box holds. */
  name: string;
  onNameChange: (name: string) => void;
}

/**
 * The row under the boxes: Load columns, a name box with Save columns, and a
 * trashcan for the selected set.
 *
 * It mounts with the panel, so the user's sets are read only once somebody opens
 * the chooser.  Loading a set ticks its boxes and puts its name in the box, so
 * pressing Save columns after further changes replaces that set; typing another
 * name saves a new one.  Enter in the name box saves too.
 */
function SavedColumnSets({
  report,
  columns,
  chosen,
  onChange,
  selectedId,
  onSelect,
  name,
  onNameChange,
}: SavedColumnSetsProps): JSX.Element {
  const nameId = useId();
  const sets = useColumnSets(report);
  const save = useSaveColumnSet(report);
  const remove = useDeleteColumnSet(report);
  const saved = sets.data ?? [];
  const selected = saved.find((set) => set.id === selectedId) ?? null;
  const trimmed = name.trim();
  const canSave = trimmed !== '' && !save.isPending;
  const failure = save.error ?? remove.error;

  function handleLoad(event: ChangeEvent<HTMLSelectElement>) {
    const set = saved.find((candidate) => String(candidate.id) === event.target.value);
    if (set === undefined) return;
    onSelect(set.id);
    onNameChange(set.name);
    onChange(columnsOfSet(columns, set.columns));
  }

  function handleSave() {
    if (!canSave) return;
    remove.reset();
    save.mutate({ name: trimmed, columns: chosen }, { onSuccess: (set) => onSelect(set.id) });
  }

  function handleNameKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'Enter') return;
    // The chooser can sit inside a filter form; Enter here saves the set instead.
    event.preventDefault();
    handleSave();
  }

  function handleDelete() {
    if (selected === null) return;
    save.reset();
    remove.mutate(selected.id, {
      onSuccess: () => {
        onSelect(null);
        onNameChange('');
      },
    });
  }

  return (
    <div className="column-chooser__sets">
      {sets.isError ? <p className="muted">Your saved columns could not be loaded.</p> : null}
      <div className="column-chooser__sets-row">
        <select
          aria-label="Load columns"
          value={selected === null ? '' : String(selected.id)}
          onChange={handleLoad}
        >
          <option value="">Load columns…</option>
          {saved.map((set) => (
            <option key={set.id} value={String(set.id)}>
              {set.name}
            </option>
          ))}
        </select>
        {selected !== null ? (
          <IconButton
            icon="trashcan"
            label={`Delete the saved set ${selected.name}`}
            onClick={handleDelete}
            disabled={remove.isPending}
          />
        ) : null}
      </div>
      <div className="column-chooser__sets-row">
        <label htmlFor={nameId} className="visually-hidden">
          Name for these columns
        </label>
        <input
          id={nameId}
          type="text"
          placeholder="Name"
          maxLength={MAX_SET_NAME}
          value={name}
          onChange={(event) => onNameChange(event.target.value)}
          onKeyDown={handleNameKeyDown}
        />
        <Button variant="quiet" small onClick={handleSave} disabled={!canSave}>
          Save columns
        </Button>
      </div>
      {failure !== null ? (
        <p role="alert" className="field__error">
          {failure.message}
        </p>
      ) : null}
    </div>
  );
}
