import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { Column } from './DataTable';
import { DataTable, sortRows, tableMinWidth } from './DataTable';

interface Row {
  id: number;
  name: string;
  hours: number | null;
}

const ROWS: Row[] = [
  { id: 1, name: 'Reyes, Marta', hours: 1200 },
  { id: 2, name: 'Delgado, Owen', hours: 90 },
  { id: 3, name: 'Adeyemi, Kofi', hours: null },
];

/**
 * Names that separate `localeCompare` from a byte-wise sort: `ångström` and
 * `Ávila` collate as `a`, and `zeta` in lower case still follows `Ávila`.
 */
const ACCENTED_ROWS: Row[] = [
  { id: 1, name: 'zeta', hours: 0 },
  { id: 2, name: 'Ávila', hours: -5 },
  { id: 3, name: 'ångström', hours: 1_000_000 },
  { id: 4, name: 'Beaumont', hours: 0 },
];

const COLUMNS: Column<Row>[] = [
  { key: 'name', header: 'Name', render: (row) => row.name, sortValue: (row) => row.name },
  {
    key: 'hours',
    header: 'Hours',
    numeric: true,
    render: (row) => row.hours ?? '—',
    sortValue: (row) => row.hours,
  },
  { key: 'actions', header: 'Actions', render: () => <span>view</span> },
];

function bodyNames(): string[] {
  const body = screen.getAllByRole('rowgroup')[1];
  return within(body!)
    .getAllByRole('row')
    .map((row) => within(row).getAllByRole('cell')[0]?.textContent ?? '');
}

describe('sortRows', () => {
  it.each<[string, Row[], 'asc' | 'desc', string[]]>([
    ['ascending', ROWS, 'asc', ['Adeyemi, Kofi', 'Delgado, Owen', 'Reyes, Marta']],
    ['descending', ROWS, 'desc', ['Reyes, Marta', 'Delgado, Owen', 'Adeyemi, Kofi']],
    ['accented, ascending', ACCENTED_ROWS, 'asc', ['ångström', 'Ávila', 'Beaumont', 'zeta']],
    ['accented, descending', ACCENTED_ROWS, 'desc', ['zeta', 'Beaumont', 'Ávila', 'ångström']],
  ])('sorts names ignoring case and accents (%s)', (_label, rows, direction, expected) => {
    expect(sortRows(rows, COLUMNS[0], direction).map((row) => row.name)).toEqual(expected);
  });

  it.each<[string, Row[], 'asc' | 'desc', (number | null)[]]>([
    ['ascending, nulls last', ROWS, 'asc', [90, 1200, null]],
    ['descending, nulls first', ROWS, 'desc', [null, 1200, 90]],
    ['negative and zero', ACCENTED_ROWS, 'asc', [-5, 0, 0, 1_000_000]],
  ])('sorts numbers numerically (%s)', (_label, rows, direction, expected) => {
    expect(sortRows(rows, COLUMNS[1], direction).map((row) => row.hours)).toEqual(expected);
  });

  it('leaves rows alone for an unsortable column', () => {
    expect(sortRows(ROWS, COLUMNS[2], 'asc')).toEqual(ROWS);
  });

  it('returns a new array rather than sorting the caller’s', () => {
    const rows = [...ROWS];
    sortRows(rows, COLUMNS[0], 'asc');
    expect(rows).toEqual(ROWS);
  });
});

describe('DataTable', () => {
  it('renders every row and column', () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} />);
    expect(screen.getAllByRole('columnheader')).toHaveLength(3);
    expect(bodyNames()).toEqual(['Reyes, Marta', 'Delgado, Owen', 'Adeyemi, Kofi']);
  });

  it('sorts when a header is clicked, and toggles direction', async () => {
    const user = userEvent.setup();
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} />);

    await user.click(screen.getByRole('button', { name: /Name/ }));
    expect(bodyNames()).toEqual(['Adeyemi, Kofi', 'Delgado, Owen', 'Reyes, Marta']);

    await user.click(screen.getByRole('button', { name: /Name/ }));
    expect(bodyNames()).toEqual(['Reyes, Marta', 'Delgado, Owen', 'Adeyemi, Kofi']);
  });

  it('reports the sorted column through aria-sort', async () => {
    const user = userEvent.setup();
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} />);
    await user.click(screen.getByRole('button', { name: /Hours/ }));
    const header = screen.getByRole('columnheader', { name: /Hours/ });
    expect(header).toHaveAttribute('aria-sort', 'ascending');
  });

  it('honors an initial sort', () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        initialSort={{ key: 'name', direction: 'asc' }}
      />,
    );
    expect(bodyNames()).toEqual(['Adeyemi, Kofi', 'Delgado, Owen', 'Reyes, Marta']);
  });

  it('delegates to the server when onSortChange is given', async () => {
    const user = userEvent.setup();
    const handleSortChange = vi.fn();
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        onSortChange={handleSortChange}
      />,
    );
    await user.click(screen.getByRole('button', { name: /Name/ }));
    expect(handleSortChange).toHaveBeenCalledWith('name', 'asc');
    // Row order is left to the server.
    expect(bodyNames()).toEqual(['Reyes, Marta', 'Delgado, Owen', 'Adeyemi, Kofi']);
  });

  it('shows the sort it is given, and toggles from it rather than from its own state', async () => {
    const user = userEvent.setup();
    const handleSortChange = vi.fn();
    const table = (sort: { key: string; direction: 'asc' | 'desc' }) => (
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        onSortChange={handleSortChange}
        sort={sort}
      />
    );
    const { rerender } = render(table({ key: 'hours', direction: 'asc' }));
    rerender(table({ key: 'name', direction: 'asc' }));

    expect(screen.getByRole('columnheader', { name: /Hours/ })).toHaveAttribute(
      'aria-sort',
      'none',
    );
    await user.click(screen.getByRole('button', { name: /Name/ }));
    expect(handleSortChange).toHaveBeenCalledWith('name', 'desc');
  });

  it('shows an empty state instead of an empty table', () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={[]}
        rowKey={(row) => row.id}
        emptyTitle="No members match"
      />,
    );
    expect(screen.getByText('No members match')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('renders export links only when URLs are supplied', () => {
    const { rerender } = render(
      <DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} />,
    );
    expect(screen.queryByRole('link', { name: /Export CSV/ })).not.toBeInTheDocument();

    rerender(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        exportCsvUrl="/api/v1/reports/members/export.csv?status=current"
        exportPdfUrl="/api/v1/reports/members/export.pdf?status=current"
      />,
    );
    expect(screen.getByRole('link', { name: /Export CSV/ })).toHaveAttribute(
      'href',
      '/api/v1/reports/members/export.csv?status=current',
    );
    expect(screen.getByRole('link', { name: /Export PDF/ })).toBeInTheDocument();
  });

  it('draws disabled export buttons carrying the reason in place of the links', () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        exportCsvUrl="/api/v1/reports/roles/export.csv"
        exportPdfUrl="/api/v1/reports/roles/export.pdf"
        exportDisabledReason="Nothing to export."
      />,
    );
    const buttons = ['Export CSV', 'Export PDF'].map((name) =>
      screen.getByRole('button', { name }),
    );
    expect(buttons.map((button) => [button.hasAttribute('disabled'), button.title])).toEqual([
      [true, 'Nothing to export.'],
      [true, 'Nothing to export.'],
    ]);
  });

  it('renders a filter bar', () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        filters={<input aria-label="Search" />}
      />,
    );
    expect(screen.getByLabelText('Search')).toBeInTheDocument();
  });
});

describe('the minimum widths of a single-line table', () => {
  const columns: Column<{ id: number; name: string }>[] = [
    { key: 'name', header: 'Name', minWidth: '16rem', render: (row) => row.name },
    { key: 'when', header: 'When', width: '9rem', render: () => '' },
    { key: 'other', header: 'Other', render: () => '' },
  ];

  it('adds every fixed width and minimum into the table least width', () => {
    expect(tableMinWidth(columns)).toBe('calc(16rem + 9rem + 6rem)');
  });

  it('sets no least width on a table whose columns name no minimum', () => {
    expect(tableMinWidth([{ key: 'a', header: 'A', render: () => '' }])).toBeUndefined();
  });

  it('starts a column with a minimum at the left edge', () => {
    render(
      <DataTable
        singleLine
        columns={columns}
        rows={[{ id: 1, name: 'Ann' }]}
        rowKey={(r) => r.id}
      />,
    );
    expect(screen.getByRole('columnheader', { name: 'Name' })).toHaveClass('data-table__text');
    expect(screen.getByRole('table')).toHaveStyle({ minWidth: 'calc(16rem + 9rem + 6rem)' });
    expect(screen.getByRole('columnheader', { name: 'Name' })).toHaveStyle({ width: '16rem' });
  });
});
