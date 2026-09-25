/**
 * The column chooser behind a report table and its two exports.
 *
 * The registry comes from the server, so the screen and the exports can never
 * offer different columns.  The chosen set always drives the CSV and the PDF; a
 * screen whose table follows it too says so in the panel's legend.  Beside the
 * Columns button, each user keeps named sets of a report's columns: **Load
 * columns** applies one, **Save columns** keeps the boxes as they stand under a
 * name.
 */
import { useId, useState } from 'react';
import type { JSX, KeyboardEvent } from 'react';

import type { ReportColumn, SavedColumnSet } from '@/portal/api/types';
import { useColumnSets, useDeleteColumnSet, useSaveColumnSet } from '@/portal/reports/api';
import type { ReportSlug } from '@/portal/reports/types';
import { Button } from './Button';
import { DeleteButton } from './DeleteButton';
import { PanelButton } from './PanelButton';

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
 * The Columns, Load columns and Save columns buttons, side by side, each opening
 * its own panel under itself.
 *
 * Columns holds the checkboxes and **Reset to the default columns**.  Load
 * columns lists the user's saved sets for this report; picking one applies it
 * and closes the panel.  Save columns keeps the chosen columns under a name.
 */
export function ColumnChooser({
  report,
  columns,
  chosen,
  onChange,
  legend = 'Columns to show and export',
}: ColumnChooserProps): JSX.Element {
  // The name box outlives its panel, and a loaded set's name goes into it, so
  // saving after further changes replaces the set that was loaded.
  const [name, setName] = useState('');

  function handleToggle(key: string) {
    onChange(toggleColumn(columns, chosen, key));
  }

  function handleLoad(set: SavedColumnSet) {
    setName(set.name);
    onChange(columnsOfSet(columns, set.columns));
  }

  return (
    <div className="column-chooser cluster">
      <PanelButton label="Columns" legend={legend}>
        {() => (
          <>
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
          </>
        )}
      </PanelButton>
      <PanelButton label="Load columns" legend="Your saved columns">
        {(handleClose) => (
          <LoadColumnSets
            report={report}
            onLoad={(set) => {
              handleLoad(set);
              handleClose();
            }}
          />
        )}
      </PanelButton>
      <PanelButton label="Save columns" legend="Save these columns">
        {(handleClose) => (
          <SaveColumnSet
            report={report}
            chosen={chosen}
            name={name}
            onNameChange={(next) => setName(next)}
            onSaved={handleClose}
          />
        )}
      </PanelButton>
    </div>
  );
}

interface LoadColumnSetsProps {
  report: ReportSlug;
  /** Called with the set whose name was picked. */
  onLoad: (set: SavedColumnSet) => void;
}

/**
 * The Load columns panel: the user's saved sets as quiet buttons, each with a
 * trashcan beside it.
 *
 * It mounts with the panel, so the sets are read only once somebody opens it.
 * Deleting a set keeps the panel open, so several can go in one visit.
 */
function LoadColumnSets({ report, onLoad: handleLoad }: LoadColumnSetsProps): JSX.Element {
  const sets = useColumnSets(report);
  const remove = useDeleteColumnSet(report);

  if (sets.isError) return <p className="muted">Your saved columns could not be loaded.</p>;
  if (sets.data === undefined) return <p className="muted">Loading…</p>;

  return (
    <>
      {sets.data.length === 0 ? <p className="muted">No saved sets yet.</p> : null}
      {sets.data.map((set) => (
        <div key={set.id} className="column-chooser__set">
          <Button variant="quiet" small onClick={() => handleLoad(set)}>
            {set.name}
          </Button>
          <DeleteButton
            label={`Delete the saved set ${set.name}`}
            onClick={() => remove.mutate(set.id)}
            disabled={remove.isPending}
          />
        </div>
      ))}
      {remove.error !== null ? (
        <p role="alert" className="field__error">
          {remove.error.message}
        </p>
      ) : null}
    </>
  );
}

interface SaveColumnSetProps {
  report: ReportSlug;
  /** The columns to save. */
  chosen: string[];
  /** What the name box holds. */
  name: string;
  onNameChange: (name: string) => void;
  /** Called once the server has kept the set. */
  onSaved: () => void;
}

/**
 * The Save columns panel: a name box and a Save button, disabled until a name is
 * typed and inert while a save runs.
 *
 * Enter in the name box saves too.  Saving under a name the user already has
 * replaces that set.  A refusal shows in the panel, which stays open.
 */
function SaveColumnSet({
  report,
  chosen,
  name,
  onNameChange,
  onSaved: handleSaved,
}: SaveColumnSetProps): JSX.Element {
  const nameId = useId();
  const save = useSaveColumnSet(report);
  const trimmed = name.trim();
  const canSave = trimmed !== '' && !save.isPending;

  function handleSave() {
    if (!canSave) return;
    save.mutate({ name: trimmed, columns: chosen }, { onSuccess: handleSaved });
  }

  function handleNameKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'Enter') return;
    // The chooser can sit inside a filter form; Enter here saves the set instead.
    event.preventDefault();
    handleSave();
  }

  return (
    <>
      <div className="column-chooser__save">
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
        {/* Only a blank name disables Save.  While the request runs the button stays
            focusable, marked aria-disabled, so a browser does not drop the focus to the
            body and the closing panel can hand it back to Save columns. */}
        <Button
          variant="quiet"
          small
          onClick={handleSave}
          disabled={trimmed === ''}
          aria-disabled={save.isPending}
        >
          Save
        </Button>
      </div>
      {save.error !== null ? (
        <p role="alert" className="field__error">
          {save.error.message}
        </p>
      ) : null}
    </>
  );
}
