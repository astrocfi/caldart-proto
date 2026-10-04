import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Column } from './DataTable';
import { DataTable, hiddenColumnsNote, sortRows, tableMinWidth } from './DataTable';

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

  it('keeps rows that tie in the order they arrived when sorting descending', () => {
    const tied: Row[] = [
      { id: 1, name: 'first', hours: 5 },
      { id: 2, name: 'second', hours: 5 },
      { id: 3, name: 'third', hours: 9 },
    ];
    expect(sortRows(tied, COLUMNS[1], 'desc').map((row) => row.name)).toEqual([
      'third',
      'first',
      'second',
    ]);
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

    expect(screen.getByRole('columnheader', { name: /Hours/ })).not.toHaveAttribute('aria-sort');
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

describe('a table fitted to a narrow container', () => {
  const columns: Column<{ id: number; name: string }>[] = [
    { key: 'name', header: 'Name', minWidth: '16rem', render: (row) => row.name },
    { key: 'actions', header: 'Actions', width: '6rem', keepInSight: true, render: () => 'Edit' },
    { key: 'type', header: 'Type', width: '7rem', dropOrder: 1, render: () => 'Operational' },
    { key: 'reason', header: 'Reason', minWidth: '10rem', wrap: true, render: () => 'Opted out' },
  ];

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('leaves out a droppable column and keeps the actions in sight', () => {
    // jsdom lays nothing out, so every container measures 0 pixels wide.
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe(): void {}
        disconnect(): void {}
      },
    );
    render(
      <DataTable
        singleLine
        columns={columns}
        rows={[{ id: 1, name: 'Ann' }]}
        rowKey={(r) => r.id}
      />,
    );
    expect([
      screen.getAllByRole('columnheader').map((header) => header.textContent),
      screen.getByRole('columnheader', { name: 'Name' }).style.width,
    ]).toEqual([['Name', 'Actions', 'Reason'], '8rem']);
  });

  it('names the column it left out, under the scroll cue', () => {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe(): void {}
        disconnect(): void {}
      },
    );
    render(
      <DataTable
        singleLine
        columns={columns}
        rows={[{ id: 1, name: 'Ann' }]}
        rowKey={(r) => r.id}
      />,
    );
    expect(
      screen.getByText('Type is hidden to fit the window. Widen it to show every column.'),
    ).toBeInTheDocument();
  });

  it('says nothing is hidden where every column shows', () => {
    render(
      <DataTable
        singleLine
        columns={columns}
        rows={[{ id: 1, name: 'Ann' }]}
        rowKey={(r) => r.id}
      />,
    );
    expect(screen.queryByText(/hidden to fit the window/)).not.toBeInTheDocument();
  });

  it('shows every column where nothing is measured', () => {
    render(
      <DataTable
        singleLine
        columns={columns}
        rows={[{ id: 1, name: 'Ann' }]}
        rowKey={(r) => r.id}
      />,
    );
    expect(screen.getAllByRole('columnheader')).toHaveLength(4);
  });

  it('lets a wrapping column run onto more lines', () => {
    render(
      <DataTable
        singleLine
        columns={columns}
        rows={[{ id: 1, name: 'Ann' }]}
        rowKey={(r) => r.id}
      />,
    );
    expect(screen.getByRole('cell', { name: 'Opted out' })).toHaveClass('data-table__wrap');
  });
});

describe('the least width of a table whose columns are all fixed', () => {
  it('adds the fixed widths even when no column names a minimum', () => {
    expect(
      tableMinWidth([
        { key: 'a', header: 'A', width: '4rem', render: () => '' },
        { key: 'b', header: 'B', render: () => '' },
      ]),
    ).toBe('calc(4rem + 6rem)');
  });
});

describe('the identifying and actions columns', () => {
  const columns: Column<Row>[] = [
    { key: 'actions', header: '', isActions: true, render: () => <button>Edit</button> },
    { key: 'name', header: 'Name', isIdentity: true, minWidth: '12rem', render: (r) => r.name },
    { key: 'hours', header: 'Hours', numeric: true, width: '5rem', render: (r) => r.hours },
  ];

  function renderTable(): void {
    render(<DataTable singleLine columns={columns} rows={ROWS} rowKey={(row) => row.id} />);
  }

  it('draws the actions column last, wherever the screen lists it', () => {
    renderTable();
    expect(screen.getAllByRole('columnheader').map((header) => header.textContent)).toEqual([
      'Name',
      'Hours',
      'Actions',
    ]);
  });

  it('heads a blank actions column "Actions" for a screen reader alone', () => {
    renderTable();
    expect(screen.getByText('Actions')).toHaveClass('visually-hidden');
  });

  it('makes the actions column wide enough for an open delete confirmation', () => {
    renderTable();
    expect(screen.getByRole('columnheader', { name: 'Actions' })).toHaveStyle({ width: '10rem' });
  });

  it('marks the identifying column so it is pinned and never wraps', () => {
    renderTable();
    expect(screen.getByRole('rowheader', { name: 'Reyes, Marta' })).toHaveClass(
      'data-table__identity',
      'data-table__nowrap',
    );
  });
});

describe('a table wider than its container', () => {
  const widths = { scrollWidth: 0, clientWidth: 0 };

  beforeEach(() => {
    vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(function (
      this: HTMLElement,
    ) {
      return this.classList.contains('table-wrap') ? widths.scrollWidth : 0;
    });
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(function (
      this: HTMLElement,
    ) {
      return this.classList.contains('table-wrap') ? widths.clientWidth : 0;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function renderTable(): void {
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} caption="3 pilots" />);
  }

  it('makes its scroll box a region a keyboard can focus, named by the caption', () => {
    widths.scrollWidth = 800;
    widths.clientWidth = 300;
    renderTable();
    expect(screen.getByRole('region', { name: '3 pilots' })).toHaveAttribute('tabindex', '0');
  });

  it('says that it scrolls sideways', () => {
    widths.scrollWidth = 800;
    widths.clientWidth = 300;
    renderTable();
    expect(screen.getByText('Scroll sideways to see every column.')).toBeInTheDocument();
  });

  it('adds no tab stop and no cue for a table that fits', () => {
    widths.scrollWidth = 300;
    widths.clientWidth = 300;
    renderTable();
    expect(screen.queryByRole('region')).not.toBeInTheDocument();
  });
});

describe('sorting cues', () => {
  it('shows the arrow and aria-sort of the sort the table opens on', () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        initialSort={{ key: 'name', direction: 'asc' }}
      />,
    );
    const header = screen.getByRole('columnheader', { name: /Name/ });
    expect([header.getAttribute('aria-sort'), header.textContent]).toEqual(['ascending', 'Name↑']);
  });

  it('draws an unsortable heading as plain words with no button', () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} />);
    expect(
      within(screen.getByRole('columnheader', { name: 'Actions' })).queryByRole('button'),
    ).not.toBeInTheDocument();
  });

  it('marks a sortable heading that is not the sorted one with a faint arrow', () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} />);
    expect(screen.getByRole('button', { name: /Name/ }).textContent).toBe('Name↕');
  });

  it('puts the arrow on the left of a right-aligned heading', () => {
    render(<DataTable columns={COLUMNS} rows={ROWS} rowKey={(row) => row.id} />);
    expect(screen.getByRole('button', { name: /Hours/ }).textContent).toBe('↕Hours');
  });
});

describe('pagination', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('says which rows the page shows', () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        pagination={{ page: 1, pageSize: 25, count: 51, onPageChange: () => undefined }}
      />,
    );
    expect(screen.getByText('Showing 1–25 of 51')).toBeInTheDocument();
  });

  it('disables Previous on the first page', () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        pagination={{ page: 1, pageSize: 25, count: 51, onPageChange: () => undefined }}
      />,
    );
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
  });

  it('asks for the next page and brings the top of the table into view', async () => {
    const user = userEvent.setup();
    const handlePageChange = vi.fn();
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        pagination={{ page: 1, pageSize: 25, count: 51, onPageChange: handlePageChange }}
      />,
    );
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect([handlePageChange.mock.calls, scrollIntoView.mock.calls]).toEqual([
      [[2]],
      [[{ block: 'start' }]],
    ]);
  });

  it('draws no pagination while one page holds every row', () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        pagination={{ page: 1, pageSize: 25, count: 3, onPageChange: () => undefined }}
      />,
    );
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });
});

describe('an empty table', () => {
  it('offers the next thing to do as a button', () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={[]}
        rowKey={(row) => row.id}
        emptyAction={<button type="button">Reset filters</button>}
      />,
    );
    expect(screen.getByRole('button', { name: 'Reset filters' })).toBeInTheDocument();
  });

  it('draws the tools at the right of the bar, with the exports', () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={[]}
        rowKey={(row) => row.id}
        tools={<button type="button">Columns</button>}
        exportCsvUrl="/x.csv"
      />,
    );
    expect(
      within(screen.getByRole('button', { name: 'Columns' }).parentElement!).getByRole('link', {
        name: 'Export CSV',
      }),
    ).toBeInTheDocument();
  });
});

describe('hiddenColumnsNote', () => {
  const all: Column<object>[] = ['Name', 'Email', 'DART', 'Phone'].map((header) => ({
    key: header.toLowerCase(),
    header,
    render: () => '',
  }));

  it('names two hidden columns and offers choosing fewer beside a chooser', () => {
    expect(hiddenColumnsNote(all, all.slice(0, 1).concat(all.slice(3)), true)).toBe(
      'Email and DART are hidden to fit the window. Widen it, or choose fewer columns.',
    );
  });

  it('lists three hidden columns with a serial comma', () => {
    expect(hiddenColumnsNote(all, all.slice(0, 1), true)).toBe(
      'Email, DART, and Phone are hidden to fit the window. Widen it, or choose fewer columns.',
    );
  });

  it('is null when every column shows', () => {
    expect(hiddenColumnsNote(all, all, true)).toBeNull();
  });
});
