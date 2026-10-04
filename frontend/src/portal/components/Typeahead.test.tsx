import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import type { JSX } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { Typeahead } from './Typeahead';
import type { SuggestionResults } from './Typeahead';

interface Place {
  id: string;
  label: string;
}

const PLACES: Place[] = [
  { id: 'mv', label: '1600 Amphitheatre Parkway, Mountain View' },
  { id: 'lv', label: '1600 Amphitheater Drive, Las Vegas' },
  { id: 'pa', label: '1600 Page Mill Road, Palo Alto' },
];

/** A suggestion hook that matches `PLACES` by substring and records every term it gets. */
function makeSuggestions(): {
  terms: string[];
  useSuggestions: (term: string) => SuggestionResults<Place>;
} {
  const terms: string[] = [];
  const useSuggestions = (term: string): SuggestionResults<Place> => {
    terms.push(term);
    if (term === '') return { data: undefined };
    const lower = term.toLowerCase();
    return { data: PLACES.filter((place) => place.label.toLowerCase().includes(lower)) };
  };
  return { terms, useSuggestions };
}

interface HarnessProps {
  onPick?: (place: Place) => void;
  useSuggestions?: (term: string) => SuggestionResults<Place>;
  itemMeta?: (place: Place) => string;
  emptyText?: string;
}

/** Holds the typed text the way a form does, and fills it with the picked place. */
function Harness({
  onPick: handleReport,
  useSuggestions = makeSuggestions().useSuggestions,
  itemMeta,
  emptyText,
}: HarnessProps): JSX.Element {
  const [value, setValue] = useState('');
  const handlePick = (place: Place): void => {
    setValue(place.label);
    handleReport?.(place);
  };
  return (
    <form onSubmit={(event) => event.preventDefault()}>
      <label htmlFor="address">Address</label>
      <Typeahead
        id="address"
        listLabel="Suggested addresses"
        value={value}
        onValueChange={(next) => setValue(next)}
        onPick={handlePick}
        useSuggestions={useSuggestions}
        itemKey={(place) => place.id}
        itemLabel={(place) => place.label}
        itemMeta={itemMeta}
        emptyText={emptyText}
      />
      <p>somewhere else</p>
      <button type="button">Next field</button>
    </form>
  );
}

async function typeAndWaitForList(text: string) {
  const user = userEvent.setup();
  render(<Harness />);
  const input = screen.getByRole('combobox', { name: 'Address' });
  await user.type(input, text);
  await screen.findByRole('listbox', { name: 'Suggested addresses' });
  return { user, input };
}

describe('Typeahead', () => {
  it('says so when a search comes back empty, given the words to say it with', async () => {
    const user = userEvent.setup();
    render(<Harness emptyText="No address matches that." />);

    await user.type(screen.getByRole('combobox', { name: 'Address' }), 'zzzz');

    expect(await screen.findByText('No address matches that.', { selector: 'p' })).toBeVisible();
  });

  it('shows nothing for an empty search without the words to say it with', async () => {
    const user = userEvent.setup();
    const { terms, useSuggestions } = makeSuggestions();
    render(<Harness useSuggestions={useSuggestions} />);

    await user.type(screen.getByRole('combobox', { name: 'Address' }), 'zzzz');
    await waitFor(() => expect(terms).toContain('zzzz'));

    expect(screen.queryByText(/matches/)).not.toBeInTheDocument();
  });

  it('is a combobox with no list until something is typed', () => {
    render(<Harness />);

    expect(screen.getByRole('combobox', { name: 'Address' })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
  });

  it('lists the matches under the box once the typing settles', async () => {
    await typeAndWaitForList('1600');

    expect(screen.getAllByRole('option').map((option) => option.textContent)).toEqual(
      PLACES.map((place) => place.label),
    );
  });

  it('asks for nothing until three characters are typed', async () => {
    const user = userEvent.setup();
    const suggestions = makeSuggestions();
    render(<Harness useSuggestions={suggestions.useSuggestions} />);

    await user.type(screen.getByRole('combobox'), '16');
    await new Promise((resolve) => window.setTimeout(resolve, 400));

    expect(suggestions.terms.filter((term) => term !== '')).toEqual([]);
  });

  it('marks the box expanded and names the list it controls', async () => {
    const { input } = await typeAndWaitForList('1600');

    expect(input).toHaveAttribute('aria-controls', screen.getByRole('listbox').id);
  });

  it('moves the active option down with ArrowDown', async () => {
    const { user, input } = await typeAndWaitForList('1600');

    await user.keyboard('{ArrowDown}{ArrowDown}');

    expect(input).toHaveAttribute('aria-activedescendant', screen.getAllByRole('option')[1]?.id);
  });

  it('wraps ArrowUp from the first option to the last', async () => {
    const { user, input } = await typeAndWaitForList('1600');

    await user.keyboard('{ArrowDown}{ArrowUp}');

    expect(input).toHaveAttribute('aria-activedescendant', screen.getAllByRole('option')[2]?.id);
  });

  it('marks the active option selected', async () => {
    const { user } = await typeAndWaitForList('1600');

    await user.keyboard('{ArrowDown}');

    expect(screen.getAllByRole('option')[0]).toHaveAttribute('aria-selected', 'true');
  });

  it('picks the active option with Enter and shuts the list', async () => {
    const handlePick = vi.fn();
    const user = userEvent.setup();
    render(<Harness onPick={handlePick} />);
    await user.type(screen.getByRole('combobox'), '1600');
    await screen.findByRole('listbox');

    await user.keyboard('{ArrowDown}{ArrowDown}{Enter}');

    expect(handlePick).toHaveBeenCalledWith(PLACES[1]);
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('leaves Enter alone while no option is active', async () => {
    const handlePick = vi.fn();
    const user = userEvent.setup();
    render(<Harness onPick={handlePick} />);
    await user.type(screen.getByRole('combobox'), '1600');
    await screen.findByRole('listbox');

    await user.keyboard('{Enter}');

    expect(handlePick).not.toHaveBeenCalled();
  });

  it('picks an option that is clicked', async () => {
    const handlePick = vi.fn();
    const user = userEvent.setup();
    render(<Harness onPick={handlePick} />);
    await user.type(screen.getByRole('combobox'), 'page');

    await user.click(await screen.findByRole('option', { name: /Page Mill/ }));

    expect(handlePick).toHaveBeenCalledWith(PLACES[2]);
  });

  it('keeps the focus in the box after a click on an option', async () => {
    const { user, input } = await typeAndWaitForList('page');

    await user.click(screen.getByRole('option', { name: /Page Mill/ }));

    expect(input).toHaveFocus();
  });

  it('writes the picked text and keeps the list shut afterwards', async () => {
    const { user, input } = await typeAndWaitForList('1600');

    await user.keyboard('{ArrowDown}{Enter}');
    await new Promise((resolve) => window.setTimeout(resolve, 400));

    expect(input).toHaveValue(PLACES[0]?.label);
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('shuts the list on Escape', async () => {
    const { user } = await typeAndWaitForList('1600');

    await user.keyboard('{Escape}');

    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('opens the list again with ArrowDown after Escape', async () => {
    const { user } = await typeAndWaitForList('1600');
    await user.keyboard('{Escape}');

    await user.keyboard('{ArrowDown}');

    expect(await screen.findByRole('listbox')).toBeInTheDocument();
  });

  it('shuts the list on a click outside it', async () => {
    const { user } = await typeAndWaitForList('1600');

    await user.click(screen.getByText('somewhere else'));

    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('shuts the list when the focus leaves the box', async () => {
    const { user } = await typeAndWaitForList('1600');

    await user.tab();

    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('shows no list when nothing matches', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByRole('combobox'), 'zzz');
    await new Promise((resolve) => window.setTimeout(resolve, 400));

    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('tells a screen reader how many suggestions there are', async () => {
    await typeAndWaitForList('1600');

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('3 suggestions'));
  });

  it("shows an item's meta after its label, in the muted face", async () => {
    const user = userEvent.setup();
    render(<Harness itemMeta={(place) => place.id.toUpperCase()} />);
    await user.type(screen.getByRole('combobox'), 'page');

    const option = await screen.findByRole('option', { name: /Page Mill/ });

    expect(option.querySelector('.typeahead__meta')).toHaveTextContent('PA');
  });

  it('names an option by its label and its meta together', async () => {
    const user = userEvent.setup();
    render(<Harness itemMeta={(place) => place.id.toUpperCase()} />);
    await user.type(screen.getByRole('combobox'), 'page');

    expect(
      await screen.findByRole('option', { name: '1600 Page Mill Road, Palo Alto PA' }),
    ).toBeInTheDocument();
  });
});
