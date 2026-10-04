/**
 * A list whose table follows its report's column chooser.
 *
 * A report list page shows the columns chosen in its `ColumnChooser`, and its CSV and
 * PDF carry the same ones, so what is on screen is what downloads.  The server's
 * registry names the columns and their order; the page names how each one draws, in
 * a record of `ReportCell`s keyed by the registry's keys.  `useColumnChoice` holds the
 * chosen keys; `reportTableColumns` turns them into the table's columns; and
 * `ColumnTools` draws the chooser, or says why it cannot.
 */
import { useMemo, useState } from 'react';
import type { JSX } from 'react';

import type { ReportColumn } from '@/portal/api/types';
import { useReportColumns } from '@/portal/reports/api';
import type { ReportSlug } from '@/portal/reports/types';
import { Button } from './Button';
import { ColumnChooser, defaultColumnKeys } from './ColumnChooser';
import type { Column } from './DataTable';

/**
 * How one report column draws in the table: everything a `Column` takes but its key
 * and heading, which come from the registry, and the `ordering` value the list's API
 * sorts it by, where it has one.  Its `dropOrder` counts only while the column is one
 * of the report's defaults.
 */
export type ReportCell<Row> = Omit<Column<Row>, 'key' | 'header'> & {
  /** The `?ordering=` value behind the column; a column without one does not sort on the server. */
  ordering?: string;
};

/** The chosen columns of one report, and what the chooser needs to change them. */
export interface ColumnChoice {
  report: ReportSlug;
  /** Every column the report can carry, in registry order; empty while loading. */
  columns: ReportColumn[];
  /** The chosen keys, in registry order: the registry's defaults until somebody chooses. */
  chosen: string[];
  setChosen: (chosen: string[]) => void;
  /** The registry could not be read. */
  isError: boolean;
  /** The registry has not arrived yet. */
  isPending: boolean;
  /**
   * The columns the table draws from: the registry once it has arrived, or the page's
   * fallback while it loads, if it cannot be read, or if it names no column.
   */
  tableColumns: readonly ReportColumn[];
  /** The keys the table shows: the chosen ones, or the fallback's defaults. */
  tableChosen: readonly string[];
}

/**
 * The column choice for `report`: the registry's defaults until the chooser changes
 * them, following a registry that is still loading.
 *
 * The table never goes without columns: until the registry arrives, and if it cannot
 * be read or names none, it draws `fallback`, the page's own copy of the report's
 * default columns.
 *
 * @param report the report whose columns are chosen.
 * @param fallback the columns the table shows without the registry, the defaults checked.
 * @returns the registry, the chosen keys, their setter, and what the table shows.
 */
export function useColumnChoice(
  report: ReportSlug,
  fallback: readonly ReportColumn[] = [],
): ColumnChoice {
  const registry = useReportColumns(report);
  const columns = useMemo(() => registry.data ?? [], [registry.data]);
  // Null means "whatever the registry calls default": the chooser has not been
  // touched, so it must follow a registry that is still loading.
  const [chosen, setChosen] = useState<string[] | null>(null);
  const chosenKeys = chosen ?? defaultColumnKeys(columns);
  const isFallback = columns.length === 0;
  return {
    report,
    columns,
    chosen: chosenKeys,
    setChosen,
    isError: registry.isError,
    isPending: registry.isPending,
    tableColumns: isFallback ? fallback : columns,
    tableChosen: isFallback ? defaultColumnKeys(fallback) : chosenKeys,
  };
}

/** A cell for a column the page has not said how to draw: a dash. */
function unknownCell<Row>(): ReportCell<Row> {
  return { render: () => '—' };
}

/**
 * The table's columns for the chosen keys, in registry order.
 *
 * Each takes its heading from the registry and its drawing from `cells`.  Only a
 * default column keeps the `dropOrder` its cell gives: a column somebody checked beyond
 * the defaults always shows, and the table scrolls sideways when it must.  Under
 * server sorting (`isServerSorted`) a column's key is its `ordering` value and a
 * column without one is unsortable; otherwise the key is the registry's.
 *
 * @param registry every column the report carries, in order.
 * @param chosen the keys to show.
 * @param cells how each key draws.
 * @param isServerSorted whether the list sorts on the server.
 * @returns the columns to hand `DataTable`.
 */
export function reportTableColumns<Row>(
  registry: readonly ReportColumn[],
  chosen: readonly string[],
  cells: Readonly<Record<string, ReportCell<Row>>>,
  isServerSorted: boolean,
): Column<Row>[] {
  return registry
    .filter((column) => chosen.includes(column.key))
    .map((column) => {
      const { ordering, ...given }: ReportCell<Row> = cells[column.key] ?? unknownCell<Row>();
      // A column the person checked, beyond the report's defaults, is never left out to
      // fit the screen: the table scrolls instead, its identifying column pinned.
      const cell = column.default ? given : { ...given, dropOrder: undefined };
      if (!isServerSorted) return { ...cell, key: column.key, header: column.label };
      return {
        ...cell,
        key: ordering ?? column.key,
        header: column.label,
        sortable: ordering !== undefined,
      };
    });
}

export interface ColumnToolsProps {
  choice: ColumnChoice;
  /** Why the columns cannot be chosen right now; the button is then disabled with it. */
  disabledReason?: string;
}

/**
 * The Columns, Load columns, and Save columns buttons for a list, or a line saying
 * the columns could not be loaded, or nothing while they load.
 */
export function ColumnTools({ choice, disabledReason }: ColumnToolsProps): JSX.Element | null {
  if (choice.isError) {
    return <p className="muted">The columns didn't load; the list shows the default ones.</p>;
  }
  if (choice.columns.length === 0) return null;
  if (disabledReason !== undefined) {
    return (
      <Button variant="quiet" small disabled title={disabledReason}>
        Columns
      </Button>
    );
  }
  const { setChosen: handleChange } = choice;
  return (
    <ColumnChooser
      report={choice.report}
      columns={choice.columns}
      chosen={choice.chosen}
      onChange={handleChange}
    />
  );
}
