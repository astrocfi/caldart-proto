import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { Button } from './Button';
import { PanelButton } from './PanelButton';

/** A panel button whose panel holds one checkbox and a Done button that closes it. */
function renderPanel() {
  return render(
    <>
      <PanelButton label="Columns" legend="Columns to show">
        {(handleClose) => (
          <>
            <label>
              <input type="checkbox" /> Name
            </label>
            <Button onClick={handleClose}>Done</Button>
          </>
        )}
      </PanelButton>
      <p>somewhere else</p>
    </>,
  );
}

describe('PanelButton', () => {
  it('keeps its panel shut until the button is pressed', () => {
    renderPanel();

    expect(screen.queryByRole('group', { name: 'Columns to show' })).toBeNull();
  });

  it('opens its panel under the button when pressed', async () => {
    renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'Columns' }));

    expect(screen.getByRole('group', { name: 'Columns to show' })).toBeInTheDocument();
  });

  it('keeps a panel of choices to its fixed height', async () => {
    renderPanel();
    await userEvent.click(screen.getByRole('button', { name: 'Columns' }));
    expect(screen.getByRole('group', { name: 'Columns to show' })).not.toHaveClass(
      'panel-button__panel--form',
    );
  });

  it('lets a panel holding a form grow to the form', async () => {
    render(
      <PanelButton label="Save as a group" legend="Save the batch as a group" isForm>
        {() => <input aria-label="Group name" />}
      </PanelButton>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Save as a group' }));
    expect(screen.getByRole('group', { name: 'Save the batch as a group' })).toHaveClass(
      'panel-button__panel--form',
    );
  });

  it('says whether the panel is open', async () => {
    renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'Columns' }));

    expect(screen.getByRole('button', { name: 'Columns' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
  });

  it('names the panel it controls', async () => {
    renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'Columns' }));

    const panel = screen.getByRole('group', { name: 'Columns to show' });
    expect(screen.getByRole('button', { name: 'Columns' })).toHaveAttribute(
      'aria-controls',
      panel.id,
    );
  });

  it('shuts the panel when the button is pressed again', async () => {
    renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'Columns' }));
    await userEvent.click(screen.getByRole('button', { name: 'Columns' }));

    expect(screen.queryByRole('group', { name: 'Columns to show' })).toBeNull();
  });

  it('stays open while its contents are used', async () => {
    renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'Columns' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Name' }));

    expect(screen.getByRole('group', { name: 'Columns to show' })).toBeInTheDocument();
  });

  it('closes on a click outside it', async () => {
    renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'Columns' }));
    await userEvent.click(screen.getByText('somewhere else'));

    expect(screen.queryByRole('group', { name: 'Columns to show' })).toBeNull();
  });

  it('closes on Escape', async () => {
    renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'Columns' }));
    await userEvent.keyboard('{Escape}');

    expect(screen.queryByRole('group', { name: 'Columns to show' })).toBeNull();
  });

  it('puts the focus back on its button after Escape from inside the panel', async () => {
    renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'Columns' }));
    await userEvent.tab();
    await userEvent.keyboard('{Escape}');

    expect(screen.getByRole('button', { name: 'Columns' })).toHaveFocus();
  });

  it('lets its contents close it, handing the focus back to the button', async () => {
    renderPanel();

    await userEvent.click(screen.getByRole('button', { name: 'Columns' }));
    await userEvent.click(screen.getByRole('button', { name: 'Done' }));

    expect(screen.getByRole('button', { name: 'Columns' })).toHaveFocus();
  });
});
