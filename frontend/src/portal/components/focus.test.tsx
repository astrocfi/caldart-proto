import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useCallback, useRef, useState } from 'react';
import type { JSX } from 'react';
import { describe, expect, it } from 'vitest';

import { ConfirmButton } from './ConfirmButton';
import { MultiSelect } from './MultiSelect';
import { Typeahead } from './Typeahead';
import { focusRefusal, rememberPlace, useFocusAfterSave, usePanelFocus } from './focus';

const AIRPORTS = ['PAO', 'PAE', 'PAN'];

/** Suggestions answered at once, for the typeahead inside a panel. */
function useAirports(term: string): { data: string[] | undefined } {
  return { data: term === '' ? undefined : AIRPORTS.filter((one) => one.startsWith(term)) };
}

/** A form opened in place that holds a typeahead and a drop-down of checkboxes. */
function FormWithPopovers(): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const [airport, setAirport] = useState('');
  const [kinds, setKinds] = useState<string[]>([]);
  const handleClose = useCallback(() => setIsOpen(false), []);
  const panelRef = usePanelFocus(isOpen ? 'new' : null, handleClose);
  return (
    <>
      <button type="button" onClick={() => setIsOpen(true)}>
        New
      </button>
      {isOpen ? (
        <div ref={panelRef}>
          <label htmlFor="airport">Airport</label>
          <Typeahead
            id="airport"
            listLabel="Airports"
            value={airport}
            onValueChange={(next) => setAirport(next)}
            onPick={(item) => setAirport(item)}
            useSuggestions={useAirports}
            itemKey={(item) => item}
            itemLabel={(item) => item}
            minLength={1}
          />
          <MultiSelect
            id="kinds"
            legend="Kinds"
            options={[
              { value: 'member', label: 'Member' },
              { value: 'friend', label: 'Friend' },
            ]}
            value={kinds}
            onChange={(next) => setKinds(next)}
          />
        </div>
      ) : null}
    </>
  );
}

/** A button that opens a form in place, the way a list screen's **Edit** does. */
function EditInPlace({ hidesOpener = false }: { hidesOpener?: boolean }): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const fallbackRef = useRef<HTMLButtonElement>(null);
  const handleClose = useCallback(() => setIsOpen(false), []);
  const panelRef = usePanelFocus(isOpen ? 'edit' : null, handleClose, fallbackRef);
  return (
    <>
      {hidesOpener && isOpen ? null : (
        <button type="button" ref={fallbackRef} onClick={() => setIsOpen(true)}>
          Edit
        </button>
      )}
      {isOpen ? (
        <div ref={panelRef}>
          <label>
            Name <input />
          </label>
          <ConfirmButton
            label="Clear it"
            choices={[{ label: 'Clear the name', onChoose: () => Promise.resolve() }]}
          />
          <button type="button" onClick={handleClose}>
            Cancel
          </button>
        </div>
      ) : null}
    </>
  );
}

/** A save button that is disabled while its request is in flight. */
function SaveButton({ isPending }: { isPending: boolean }): JSX.Element {
  const formRef = useRef<HTMLFormElement>(null);
  useFocusAfterSave(formRef, isPending);
  return (
    <form ref={formRef}>
      <button type="submit" disabled={isPending}>
        Save
      </button>
    </form>
  );
}

describe('usePanelFocus', () => {
  it('moves the focus to the first field as the panel opens', async () => {
    render(<EditInPlace />);

    await userEvent.click(screen.getByRole('button', { name: 'Edit' }));

    expect(screen.getByRole('textbox', { name: 'Name' })).toHaveFocus();
  });

  it('closes the panel on Escape', async () => {
    render(<EditInPlace />);

    await userEvent.click(screen.getByRole('button', { name: 'Edit' }));
    await userEvent.keyboard('{Escape}');

    expect(screen.queryByRole('textbox', { name: 'Name' })).toBeNull();
  });

  it('gives the focus back to the control that opened the panel as it closes', async () => {
    render(<EditInPlace />);

    await userEvent.click(screen.getByRole('button', { name: 'Edit' }));
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.getByRole('button', { name: 'Edit' })).toHaveFocus();
  });

  it('gives the focus to the fallback when the opener left the page with the panel open', async () => {
    render(<EditInPlace hidesOpener />);

    await userEvent.click(screen.getByRole('button', { name: 'Edit' }));
    await userEvent.keyboard('{Escape}');

    expect(screen.getByRole('button', { name: 'Edit' })).toHaveFocus();
  });

  it('leaves the panel open when Escape closes a confirmation inside it', async () => {
    render(<EditInPlace />);

    await userEvent.click(screen.getByRole('button', { name: 'Edit' }));
    await userEvent.click(screen.getByRole('button', { name: 'Clear it' }));
    await userEvent.keyboard('{Escape}');

    expect(screen.getByRole('textbox', { name: 'Name' })).toBeInTheDocument();
  });
});

describe('usePanelFocus around a popover', () => {
  it('closes an open typeahead list on Escape and leaves the form open', async () => {
    render(<FormWithPopovers />);

    await userEvent.click(screen.getByRole('button', { name: 'New' }));
    await userEvent.type(screen.getByRole('combobox', { name: 'Airport' }), 'PA');
    await screen.findByRole('listbox', { name: 'Airports' });
    await userEvent.keyboard('{Escape}');

    expect(screen.getByRole('combobox', { name: 'Airport' })).toBeInTheDocument();
  });

  it('closes an open drop-down of checkboxes on Escape and leaves the form open', async () => {
    render(<FormWithPopovers />);

    await userEvent.click(screen.getByRole('button', { name: 'New' }));
    await userEvent.click(screen.getByRole('button', { name: /Any/ }));
    await userEvent.keyboard('{Escape}');

    expect(screen.getByRole('combobox', { name: 'Airport' })).toBeInTheDocument();
  });

  it('closes the form on an Escape pressed once the popover is shut', async () => {
    render(<FormWithPopovers />);

    await userEvent.click(screen.getByRole('button', { name: 'New' }));
    await userEvent.click(screen.getByRole('button', { name: /Any/ }));
    await userEvent.keyboard('{Escape}');
    await userEvent.keyboard('{Escape}');

    expect(screen.queryByRole('combobox', { name: 'Airport' })).toBeNull();
  });
});

describe('focusRefusal', () => {
  it('focuses the first field marked invalid', () => {
    render(
      <form data-testid="form">
        <input aria-label="First" />
        <input aria-label="Second" aria-invalid="true" />
        <input aria-label="Third" aria-invalid="true" />
      </form>,
    );

    focusRefusal(screen.getByTestId('form'));

    expect(screen.getByRole('textbox', { name: 'Second' })).toHaveFocus();
  });

  it('counts the fields marked invalid', () => {
    render(
      <form data-testid="form">
        <input aria-label="Second" aria-invalid="true" />
        <input aria-label="Third" aria-invalid="true" />
      </form>,
    );

    expect(focusRefusal(screen.getByTestId('form'))).toBe(2);
  });

  it("focuses the form's own complaint when no field is marked", () => {
    render(
      <form data-testid="form">
        <p role="alert">That member was deleted.</p>
        <input aria-label="First" />
      </form>,
    );

    focusRefusal(screen.getByTestId('form'));

    expect(screen.getByRole('alert')).toHaveFocus();
  });
});

describe('useFocusAfterSave', () => {
  it('puts the focus back on the submit button once the save ends', () => {
    const { rerender } = render(<SaveButton isPending={false} />);
    screen.getByRole('button', { name: 'Save' }).focus();
    rerender(<SaveButton isPending />);
    // A disabled button drops the focus, as a browser does.
    screen.getByRole('button', { name: 'Save' }).blur();
    rerender(<SaveButton isPending={false} />);

    expect(screen.getByRole('button', { name: 'Save' })).toHaveFocus();
  });

  it('leaves the focus where something else has put it', () => {
    const { rerender } = render(
      <>
        <input aria-label="Name" />
        <SaveButton isPending />
      </>,
    );
    screen.getByRole('textbox', { name: 'Name' }).focus();
    rerender(
      <>
        <input aria-label="Name" />
        <SaveButton isPending={false} />
      </>,
    );

    expect(screen.getByRole('textbox', { name: 'Name' })).toHaveFocus();
  });
});

describe('rememberPlace', () => {
  it('gives the control itself while it is still on the page', () => {
    render(
      <ul>
        <li>
          <button type="button">Remove</button>
        </li>
      </ul>,
    );
    const button = screen.getByRole('button', { name: 'Remove' });

    expect(rememberPlace(button)()).toBe(button);
  });

  it('gives the list item the control sat in once the control is gone', () => {
    const { rerender } = render(
      <ul>
        <li>
          <button type="button">Remove</button>
        </li>
      </ul>,
    );
    const place = rememberPlace(screen.getByRole('button', { name: 'Remove' }));
    rerender(
      <ul>
        <li>Removed</li>
      </ul>,
    );

    expect(place()).toBe(screen.getByRole('listitem'));
  });
});
