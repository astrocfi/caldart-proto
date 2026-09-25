import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import type { SavedColumnSet } from '@/portal/api/types';
import { TEST_COLUMNS } from '@test/fixtures/finance';
import { API, columnSetHandlers } from '@test/handlers';
import type { ColumnSetRequest } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { ColumnChooser, columnsOfSet, defaultColumnKeys, toggleColumn } from './ColumnChooser';

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

describe('columnsOfSet', () => {
  it('puts a saved set in registry order', () => {
    expect(columnsOfSet(TEST_COLUMNS, ['status', 'name', 'paid_on'])).toEqual([
      'paid_on',
      'name',
      'status',
    ]);
  });

  it('drops a key the registry no longer carries', () => {
    expect(columnsOfSet(TEST_COLUMNS, ['name', 'retired_column'])).toEqual(['name']);
  });

  it('falls back to the defaults when none of the keys is left', () => {
    expect(columnsOfSet(TEST_COLUMNS, ['retired_column'])).toEqual(
      defaultColumnKeys(TEST_COLUMNS),
    );
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

  return (
    <ColumnChooser
      report="payments"
      columns={TEST_COLUMNS}
      chosen={chosen}
      onChange={handleChange}
    />
  );
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

  it('puts the focus back on the Columns button after Escape', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness onChange={handleNothing} />);

    await user.click(screen.getByRole('button', { name: 'Columns' }));
    await user.tab();
    await user.keyboard('{Escape}');

    expect(screen.getByRole('button', { name: 'Columns' })).toHaveFocus();
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

/** Two saved sets of the payments report, as the server lists them. */
const SAVED_SETS: SavedColumnSet[] = [
  { id: 7, name: 'Audit', columns: ['paid_on', 'receipt_number', 'total'] },
  { id: 9, name: 'Short', columns: ['name', 'total'] },
];

/** Render the chooser over `sets`, open its panel, and return the requests it makes. */
async function openWithSets(
  sets: SavedColumnSet[],
  onChange: (chosen: string[]) => void = handleNothing,
) {
  const requests: ColumnSetRequest[] = [];
  server.use(...columnSetHandlers('payments', sets, requests));
  const user = userEvent.setup();
  renderWithProviders(<Harness onChange={onChange} />);
  await user.click(screen.getByRole('button', { name: 'Columns' }));
  return { user, requests };
}

/** The names the Load columns drop-down offers, after its placeholder. */
function loadOptions(): string[] {
  const select = screen.getByRole('combobox', { name: 'Load columns' });
  return Array.from((select as HTMLSelectElement).options).map((option) => option.text);
}

describe('ColumnChooser saved sets', () => {
  it("offers the caller's saved sets by name under Load columns", async () => {
    await openWithSets(SAVED_SETS);

    expect(await screen.findByRole('option', { name: 'Short' })).toBeInTheDocument();
    expect(loadOptions()).toEqual(['Load columns…', 'Audit', 'Short']);
  });

  it('asks for the sets of the report it is choosing columns for', async () => {
    const { requests } = await openWithSets(SAVED_SETS);

    await screen.findByRole('option', { name: 'Audit' });
    expect(requests[0]?.url).toMatch(/\/reports\/payments\/column-sets$/);
  });

  it('does not ask for the sets until the panel opens', () => {
    const requests: ColumnSetRequest[] = [];
    server.use(...columnSetHandlers('payments', SAVED_SETS, requests));
    renderWithProviders(<Harness onChange={handleNothing} />);

    expect(requests).toEqual([]);
  });

  it("loads a saved set's columns", async () => {
    const handleChange = vi.fn();
    const { user } = await openWithSets(SAVED_SETS, handleChange);

    await screen.findByRole('option', { name: 'Audit' });
    await user.selectOptions(screen.getByRole('combobox', { name: 'Load columns' }), 'Audit');

    expect(handleChange).toHaveBeenLastCalledWith(['paid_on', 'receipt_number', 'total']);
  });

  it('keeps the boxes open for editing after a set is loaded', async () => {
    const { user } = await openWithSets(SAVED_SETS);

    await screen.findByRole('option', { name: 'Short' });
    await user.selectOptions(screen.getByRole('combobox', { name: 'Load columns' }), 'Short');
    await user.click(screen.getByRole('checkbox', { name: 'Fee' }));

    expect(screen.getByRole('checkbox', { name: 'Fee' })).toBeChecked();
  });

  it('puts the loaded name in the name box, so saving again replaces that set', async () => {
    const { user } = await openWithSets(SAVED_SETS);

    await screen.findByRole('option', { name: 'Short' });
    await user.selectOptions(screen.getByRole('combobox', { name: 'Load columns' }), 'Short');

    expect(screen.getByRole('textbox', { name: 'Name for these columns' })).toHaveValue('Short');
  });

  it('keeps Save columns disabled until the box has a name', async () => {
    const { user } = await openWithSets([]);

    await user.type(screen.getByRole('textbox', { name: 'Name for these columns' }), '   ');

    expect(screen.getByRole('button', { name: 'Save columns' })).toBeDisabled();
  });

  it('saves the chosen columns under the name typed', async () => {
    const { user, requests } = await openWithSets([]);

    await user.click(screen.getByRole('checkbox', { name: 'Receipt' }));
    await user.type(screen.getByRole('textbox', { name: 'Name for these columns' }), 'Audit');
    await user.click(screen.getByRole('button', { name: 'Save columns' }));

    await screen.findByRole('option', { name: 'Audit' });
    expect(requests.find((request) => request.method === 'POST')?.body).toEqual({
      name: 'Audit',
      columns: defaultColumnKeys(TEST_COLUMNS).toSpliced(1, 0, 'receipt_number'),
    });
  });

  it('selects a set it has just saved in the drop-down', async () => {
    const { user } = await openWithSets(SAVED_SETS);

    await user.type(screen.getByRole('textbox', { name: 'Name for these columns' }), 'Board');
    await user.click(screen.getByRole('button', { name: 'Save columns' }));

    const board = await screen.findByRole('option', { name: 'Board' });
    expect((board as HTMLOptionElement).selected).toBe(true);
  });

  it('replaces a set saved under a name already in use rather than adding another', async () => {
    const { user } = await openWithSets(SAVED_SETS);

    await screen.findByRole('option', { name: 'Short' });
    await user.type(screen.getByRole('textbox', { name: 'Name for these columns' }), 'Short');
    await user.click(screen.getByRole('button', { name: 'Save columns' }));

    await screen.findByRole('button', { name: 'Delete the saved set Short' });
    expect(loadOptions()).toEqual(['Load columns…', 'Audit', 'Short']);
  });

  it("shows the server's reason when a save is refused", async () => {
    const { user } = await openWithSets([]);
    server.use(
      http.post(`${API}/reports/payments/column-sets`, () =>
        HttpResponse.json({ name: ['Ensure this field has no more than 60 characters.'] }, {
          status: 400,
        }),
      ),
    );

    await user.type(screen.getByRole('textbox', { name: 'Name for these columns' }), 'Audit');
    await user.click(screen.getByRole('button', { name: 'Save columns' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Ensure this field has no more than 60 characters.',
    );
  });

  it('offers no trashcan until a saved set is selected', async () => {
    await openWithSets(SAVED_SETS);

    await screen.findByRole('option', { name: 'Audit' });
    expect(screen.queryByRole('button', { name: /Delete the saved set/ })).toBeNull();
  });

  it('deletes the selected set with the trashcan', async () => {
    const { user, requests } = await openWithSets(SAVED_SETS);

    await screen.findByRole('option', { name: 'Audit' });
    await user.selectOptions(screen.getByRole('combobox', { name: 'Load columns' }), 'Audit');
    await user.click(screen.getByRole('button', { name: 'Delete the saved set Audit' }));

    await waitFor(() => expect(loadOptions()).toEqual(['Load columns…', 'Short']));
    expect(requests.find((request) => request.method === 'DELETE')?.url).toMatch(
      /\/reports\/payments\/column-sets\/7$/,
    );
  });

  it('says so when the saved sets cannot be read', async () => {
    server.use(
      http.get(`${API}/reports/payments/column-sets`, () =>
        HttpResponse.json({ detail: 'Server error.' }, { status: 500 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<Harness onChange={handleNothing} />);

    await user.click(screen.getByRole('button', { name: 'Columns' }));

    expect(await screen.findByText('Your saved columns could not be loaded.')).toBeInTheDocument();
  });
});
