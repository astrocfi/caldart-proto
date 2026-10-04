import { describe, expect, it } from 'vitest';

import type { ReportColumn } from '@/portal/api/types';
import type { ReportCell } from './reportTable';
import { reportTableColumns } from './reportTable';

interface Row {
  name: string;
  phone: string;
}

const REGISTRY: ReportColumn[] = [
  { key: 'name', label: 'Name', default: true },
  { key: 'phone', label: 'Phone', default: true },
  { key: 'notes', label: 'Notes', default: false },
];

const CELLS: Record<string, ReportCell<Row>> = {
  name: { ordering: 'last_name', isIdentity: true, render: (row) => row.name },
  phone: { noWrap: true, render: (row) => row.phone },
};

describe('reportTableColumns', () => {
  it('shows the chosen columns in registry order, headed by the registry', () => {
    const columns = reportTableColumns(REGISTRY, ['phone', 'name'], CELLS, false);
    expect(columns.map((column) => column.header)).toEqual(['Name', 'Phone']);
  });

  it('keys a server-sorted column by its ordering value', () => {
    const [name] = reportTableColumns(REGISTRY, ['name'], CELLS, true);
    expect([name?.key, name?.sortable]).toEqual(['last_name', true]);
  });

  it('makes a column with no ordering value unsortable on the server', () => {
    const [phone] = reportTableColumns(REGISTRY, ['phone'], CELLS, true);
    expect(phone?.sortable).toBe(false);
  });

  it('keeps the layout the page gives a cell', () => {
    const [name] = reportTableColumns(REGISTRY, ['name'], CELLS, false);
    expect(name?.isIdentity).toBe(true);
  });

  it('draws a dash for a column the page has no cell for', () => {
    const [notes] = reportTableColumns(REGISTRY, ['notes'], CELLS, false);
    expect(notes?.render({ name: 'Ann', phone: '' })).toBe('—');
  });
});
