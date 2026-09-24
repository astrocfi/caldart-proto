import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { TEST_COLUMNS } from '@test/fixtures/finance';
import { renderWithProviders } from '@test/render';
import { ColumnChooser, defaultColumnKeys, toggleColumn } from './ColumnChooser';

describe('defaultColumnKeys', () => {
  it('takes the registry at its word about which columns are default', () => {
    expect(defaultColumnKeys(TEST_COLUMNS)).not.toContain('receipt_number');
  });
});

describe('toggleColumn', () => {
  it('adds a column that was not chosen', () => {
    expect(toggleColumn(TEST_COLUMNS, ['name'], 'total')).toEqual(['name', 'total']);
  });

  it('removes a column that was', () => {
    expect(toggleColumn(TEST_COLUMNS, ['name', 'total'], 'total')).toEqual(['name']);
  });

  it('refuses to remove the last column, which would export the defaults instead', () => {
    expect(toggleColumn(TEST_COLUMNS, ['name'], 'name')).toEqual(['name']);
  });

  it('keeps the chosen columns in registry order however they were ticked', () => {
    expect(toggleColumn(TEST_COLUMNS, ['total', 'name'], 'paid_on')).toEqual([
      'paid_on',
      'name',
      'total',
    ]);
  });
});

/** A handler for the cases that do not read what the chooser reported. */
const handleNothing = vi.fn();

/** The chooser wired to state, as a screen wires it. */
function Harness({ onChange }: { onChange: (chosen: string[]) => void }) {
  const [chosen, setChosen] = useState(defaultColumnKeys(TEST_COLUMNS));

  function handleChange(next: string[]) {
    setChosen(next);
    onChange(next);
  }

  return <ColumnChooser columns={TEST_COLUMNS} chosen={chosen} onChange={handleChange} />;
}

describe('ColumnChooser', () => {
  it('keeps the list shut until it is asked for', () => {
    renderWithProviders(<Harness onChange={handleNothing} />);

    expect(screen.queryByRole('checkbox')).toBeNull();
  });

  it('offers every column the registry names', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness onChange={handleNothing} />);

    await user.click(screen.getByRole('button', { name: 'Columns' }));

    expect(screen.getAllByRole('checkbox')).toHaveLength(TEST_COLUMNS.length);
  });

  it('reports the column that was ticked', async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();
    renderWithProviders(<Harness onChange={handleChange} />);

    await user.click(screen.getByRole('button', { name: 'Columns' }));
    await user.click(screen.getByRole('checkbox', { name: 'Receipt' }));

    expect(handleChange).toHaveBeenCalledWith(expect.arrayContaining(['receipt_number']));
  });

  it('closes on a click outside it', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <Harness onChange={handleNothing} />
        <p>somewhere else</p>
      </>,
    );

    await user.click(screen.getByRole('button', { name: 'Columns' }));
    await user.click(screen.getByText('somewhere else'));

    expect(screen.queryByRole('checkbox')).toBeNull();
  });

  it('closes on Escape', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness onChange={handleNothing} />);

    await user.click(screen.getByRole('button', { name: 'Columns' }));
    await user.keyboard('{Escape}');

    expect(screen.queryByRole('checkbox')).toBeNull();
  });

  it('stays open while the boxes are being ticked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness onChange={handleNothing} />);

    await user.click(screen.getByRole('button', { name: 'Columns' }));
    await user.click(screen.getByRole('checkbox', { name: 'Receipt' }));

    expect(screen.getAllByRole('checkbox')).toHaveLength(TEST_COLUMNS.length);
  });

  it('puts the default columns back', async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();
    renderWithProviders(<Harness onChange={handleChange} />);

    await user.click(screen.getByRole('button', { name: 'Columns' }));
    await user.click(screen.getByRole('checkbox', { name: 'Receipt' }));
    await user.click(screen.getByRole('button', { name: /Reset to the default columns/ }));

    expect(handleChange).toHaveBeenLastCalledWith(defaultColumnKeys(TEST_COLUMNS));
  });
});
