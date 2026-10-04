/**
 * Reading a `DataTable`'s headings in a test.
 *
 * A sortable heading carries an arrow (up, down, or both ways) beside its words, hidden
 * from a screen reader; these helpers read the words alone.
 */
import { within } from '@testing-library/react';

/** The arrows a sortable heading draws beside its words. */
const SORT_ARROWS = /[↕↑↓]/g;

/**
 * A heading's words, without its sort arrow.
 *
 * @param header a `columnheader` element.
 * @returns its text, the arrow left out.
 */
export function headerWords(header: HTMLElement): string {
  return (header.textContent ?? '').replace(SORT_ARROWS, '');
}

/**
 * Every heading of `table`, in order, as words.
 *
 * @param table a `table` element.
 * @returns the headings' words, the arrows left out.
 */
export function tableHeaders(table: HTMLElement): string[] {
  return within(table).getAllByRole('columnheader').map(headerWords);
}

/**
 * Every cell of a body row, in order, its row header (the identifying column) among
 * them, as the columns line up under the headings.
 *
 * @param row a `row` element.
 * @returns its `th` and `td` cells.
 */
export function rowCells(row: HTMLElement): HTMLElement[] {
  return [...row.querySelectorAll<HTMLElement>(':scope > th, :scope > td')];
}
