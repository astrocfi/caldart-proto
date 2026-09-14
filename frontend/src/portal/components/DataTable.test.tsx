import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { Column } from './DataTable';
import { DataTable, sortRows } from './DataTable';

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
  it('sorts strings case-insensitively', () => {
    const sorted = sortRows(ROWS, COLUMNS[0], 'asc').map((row) => row.name);
    expect(sorted).toEqual(['Adeyemi, Kofi', 'Delgado, Owen', 'Reyes, Marta']);
  });

  it('reverses for descending', () => {
    const sorted = sortRows(ROWS, COLUMNS[0], 'desc').map((row) => row.name);
    expect(sorted).toEqual(['Reyes, Marta', 'Delgado, Owen', 'Adeyemi, Kofi']);
  });

  it('sorts numbers numerically and puts nulls last', () => {
    const sorted = sortRows(ROWS, COLUMNS[1], 'asc').map((row) => row.hours);
    expect(sorted).toEqual([90, 1200, null]);
  });

  it('leaves rows alone for an unsortable column', () => {
    expect(sortRows(ROWS, COLUMNS[2], 'asc')).toEqual(ROWS);
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
    const onSortChange = vi.fn();
    render(
      <DataTable
        columns={COLUMNS}
        rows={ROWS}
        rowKey={(row) => row.id}
        onSortChange={onSortChange}
      />,
    );
    await user.click(screen.getByRole('button', { name: /Name/ }));
    expect(onSortChange).toHaveBeenCalledWith('name', 'asc');
    // Row order is left to the server.
    expect(bodyNames()).toEqual(['Reyes, Marta', 'Delgado, Owen', 'Adeyemi, Kofi']);
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
        exportCsvUrl="/api/v1/admin/members/export.csv?status=current"
        exportPdfUrl="/api/v1/admin/members/export.pdf?status=current"
      />,
    );
    expect(screen.getByRole('link', { name: /Export CSV/ })).toHaveAttribute(
      'href',
      '/api/v1/admin/members/export.csv?status=current',
    );
    expect(screen.getByRole('link', { name: /Export PDF/ })).toBeInTheDocument();
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
