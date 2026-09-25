import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { useState } from 'react';
import type { FormEvent } from 'react';
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
    expect(columnsOfSet(TEST_COLUMNS, ['retired_column'])).toEqual(defaultColumnKeys(TEST_COLUMNS));
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

/** Render the chooser over `sets`, open the panel `button` names, and return the requests. */
async function openWithSets(
  sets: SavedColumnSet[],
  button: 'Columns' | 'Load columns' | 'Save columns',
  handleChange: (chosen: string[]) => void = handleNothing,
) {
  const requests: ColumnSetRequest[] = [];
  server.use(...columnSetHandlers('payments', sets, requests));
  const user = userEvent.setup();
  renderWithProviders(<Harness onChange={handleChange} />);
  await user.click(screen.getByRole('button', { name: button }));
  return { user, requests };
}

/** The Load columns panel. */
function loadPanel(): HTMLElement {
  return screen.getByRole('group', { name: 'Your saved columns' });
}

/** The Save columns panel. */
function savePanel(): HTMLElement {
  return screen.getByRole('group', { name: 'Save these columns' });
}

/** The names the Load columns panel offers, in order. */
function loadNames(): string[] {
  return within(loadPanel())
    .getAllByRole('button')
    .filter((button) => !button.getAttribute('aria-label')?.startsWith('Delete'))
    .map((button) => button.textContent ?? '');
}

describe('ColumnChooser buttons', () => {
  it('puts Load columns and Save columns beside Columns rather than in its panel', async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness onChange={handleNothing} />);

    await user.click(screen.getByRole('button', { name: 'Columns' }));

    const panel = screen.getByRole('group', { name: 'Columns to show and export' });
    expect(
      within(panel)
        .getAllByRole('button')
        .map((button) => button.textContent),
    ).toEqual(['Reset to the default columns']);
  });

  it('shows the three buttons while every panel is shut', () => {
    renderWithProviders(<Harness onChange={handleNothing} />);

    expect(
      ['Columns', 'Load columns', 'Save columns'].map((name) =>
        screen.getByRole('button', { name }).getAttribute('aria-expanded'),
      ),
    ).toEqual(['false', 'false', 'false']);
  });
});

describe('ColumnChooser Load columns', () => {
  it("lists the caller's saved sets by name", async () => {
    await openWithSets(SAVED_SETS, 'Load columns');

    await screen.findByRole('button', { name: 'Short' });
    expect(loadNames()).toEqual(['Audit', 'Short']);
  });

  it('asks for the sets of the report it is choosing columns for', async () => {
    const { requests } = await openWithSets(SAVED_SETS, 'Load columns');

    await screen.findByRole('button', { name: 'Audit' });
    expect(requests[0]?.url).toMatch(/\/reports\/payments\/column-sets$/);
  });

  it('does not ask for the sets until the panel opens', async () => {
    const requests: ColumnSetRequest[] = [];
    server.use(...columnSetHandlers('payments', SAVED_SETS, requests));
    const user = userEvent.setup();
    renderWithProviders(<Harness onChange={handleNothing} />);
    await screen.findByRole('button', { name: 'Load columns' });
    // Give a fetch started on mount the time to reach msw before looking.
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(requests).toEqual([]);

    await user.click(screen.getByRole('button', { name: 'Load columns' }));

    await waitFor(() => expect(requests).toHaveLength(1));
  });

  it('says so when there are no saved sets', async () => {
    await openWithSets([], 'Load columns');

    expect(await within(loadPanel()).findByText('No saved sets yet.')).toBeInTheDocument();
  });

  it("applies a saved set's columns when its name is picked", async () => {
    const handleChange = vi.fn();
    const { user } = await openWithSets(SAVED_SETS, 'Load columns', handleChange);

    await user.click(await screen.findByRole('button', { name: 'Audit' }));

    expect(handleChange).toHaveBeenLastCalledWith(['paid_on', 'receipt_number', 'total']);
  });

  it('closes the panel once a set is picked', async () => {
    const { user } = await openWithSets(SAVED_SETS, 'Load columns');

    await user.click(await screen.findByRole('button', { name: 'Audit' }));

    expect(screen.queryByRole('group', { name: 'Your saved columns' })).toBeNull();
  });

  it('hands the focus back to Load columns once a set is picked', async () => {
    const { user } = await openWithSets(SAVED_SETS, 'Load columns');

    await user.click(await screen.findByRole('button', { name: 'Audit' }));

    expect(screen.getByRole('button', { name: 'Load columns' })).toHaveFocus();
  });

  it('puts a picked name in the Save columns box, so saving again replaces that set', async () => {
    const { user } = await openWithSets(SAVED_SETS, 'Load columns');

    await user.click(await screen.findByRole('button', { name: 'Short' }));
    await user.click(screen.getByRole('button', { name: 'Save columns' }));

    expect(screen.getByRole('textbox', { name: 'Name for these columns' })).toHaveValue('Short');
  });

  it('deletes a set with the trashcan beside its name', async () => {
    const { user, requests } = await openWithSets(SAVED_SETS, 'Load columns');

    await user.click(await screen.findByRole('button', { name: 'Delete the saved set Audit' }));

    await waitFor(() => expect(loadNames()).toEqual(['Short']));
    expect(requests.find((request) => request.method === 'DELETE')?.url).toMatch(
      /\/reports\/payments\/column-sets\/7$/,
    );
  });

  it('keeps the panel open after a delete', async () => {
    const { user } = await openWithSets(SAVED_SETS, 'Load columns');

    await user.click(await screen.findByRole('button', { name: 'Delete the saved set Audit' }));

    await waitFor(() => expect(loadNames()).toEqual(['Short']));
    expect(loadPanel()).toBeInTheDocument();
  });

  it("shows the server's reason when a delete is refused", async () => {
    const { user } = await openWithSets(SAVED_SETS, 'Load columns');
    server.use(
      http.delete(`${API}/reports/payments/column-sets/7`, () =>
        HttpResponse.json({ detail: 'Not found.' }, { status: 404 }),
      ),
    );

    await user.click(await screen.findByRole('button', { name: 'Delete the saved set Audit' }));

    expect(await within(loadPanel()).findByRole('alert')).toHaveTextContent('Not found.');
  });

  it('says so when the saved sets cannot be read', async () => {
    server.use(
      http.get(`${API}/reports/payments/column-sets`, () =>
        HttpResponse.json({ detail: 'Server error.' }, { status: 500 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<Harness onChange={handleNothing} />);

    await user.click(screen.getByRole('button', { name: 'Load columns' }));

    expect(await screen.findByText('Your saved columns could not be loaded.')).toBeInTheDocument();
  });
});

describe('ColumnChooser Save columns', () => {
  it('keeps Save disabled until the box has a name', async () => {
    const { user } = await openWithSets([], 'Save columns');

    await user.type(screen.getByRole('textbox', { name: 'Name for these columns' }), '   ');

    expect(within(savePanel()).getByRole('button', { name: 'Save' })).toBeDisabled();
  });

  it('saves the chosen columns under the name typed', async () => {
    const { user, requests } = await openWithSets([], 'Columns');

    await user.click(screen.getByRole('checkbox', { name: 'Receipt' }));
    await user.click(screen.getByRole('button', { name: 'Save columns' }));
    await user.type(screen.getByRole('textbox', { name: 'Name for these columns' }), 'Audit');
    await user.click(within(savePanel()).getByRole('button', { name: 'Save' }));

    await waitFor(() =>
      expect(requests.find((request) => request.method === 'POST')?.body).toEqual({
        name: 'Audit',
        columns: ['paid_on', 'receipt_number', 'name', 'total', 'fee', 'net', 'refunded', 'status'],
      }),
    );
  });

  it('closes the panel once the save succeeds', async () => {
    const { user } = await openWithSets([], 'Save columns');

    await user.type(screen.getByRole('textbox', { name: 'Name for these columns' }), 'Audit');
    await user.click(within(savePanel()).getByRole('button', { name: 'Save' }));

    await waitFor(() =>
      expect(screen.queryByRole('group', { name: 'Save these columns' })).toBeNull(),
    );
  });

  it('saves when Enter is pressed in the name box', async () => {
    const { user, requests } = await openWithSets([], 'Save columns');

    await user.type(
      screen.getByRole('textbox', { name: 'Name for these columns' }),
      'Audit{Enter}',
    );

    await waitFor(() =>
      expect(requests.find((request) => request.method === 'POST')?.body).toEqual({
        name: 'Audit',
        columns: defaultColumnKeys(TEST_COLUMNS),
      }),
    );
  });

  it('does not submit a surrounding form when Enter saves', async () => {
    const requests: ColumnSetRequest[] = [];
    server.use(...columnSetHandlers('payments', [], requests));
    const handleSubmit = vi.fn((event: FormEvent) => event.preventDefault());
    const user = userEvent.setup();
    renderWithProviders(
      <form onSubmit={handleSubmit}>
        <Harness onChange={handleNothing} />
        <button type="submit">Search</button>
      </form>,
    );

    await user.click(screen.getByRole('button', { name: 'Save columns' }));
    await user.type(
      screen.getByRole('textbox', { name: 'Name for these columns' }),
      'Audit{Enter}',
    );

    await waitFor(() => expect(requests.some((request) => request.method === 'POST')).toBe(true));
    expect(handleSubmit).not.toHaveBeenCalled();
  });

  it('replaces a set saved under a name already in use rather than adding another', async () => {
    const { user } = await openWithSets(SAVED_SETS, 'Save columns');

    await user.type(screen.getByRole('textbox', { name: 'Name for these columns' }), 'Short');
    await user.click(within(savePanel()).getByRole('button', { name: 'Save' }));
    await waitFor(() =>
      expect(screen.queryByRole('group', { name: 'Save these columns' })).toBeNull(),
    );
    await user.click(screen.getByRole('button', { name: 'Load columns' }));

    await screen.findByRole('button', { name: 'Short' });
    expect(loadNames()).toEqual(['Audit', 'Short']);
  });

  it("shows the server's reason in the panel when a save is refused", async () => {
    const { user } = await openWithSets([], 'Save columns');
    server.use(
      http.post(`${API}/reports/payments/column-sets`, () =>
        HttpResponse.json(
          { name: ['Ensure this field has no more than 60 characters.'] },
          { status: 400 },
        ),
      ),
    );

    await user.type(screen.getByRole('textbox', { name: 'Name for these columns' }), 'Audit');
    await user.click(within(savePanel()).getByRole('button', { name: 'Save' }));

    expect(await within(savePanel()).findByRole('alert')).toHaveTextContent(
      'Ensure this field has no more than 60 characters.',
    );
  });
});
