import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import type { JSX } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@test/render';
import { ConfirmButton } from './ConfirmButton';

/** A table cell whose confirmation, once it goes through, replaces itself with "Off". */
function TurnOffRow(): JSX.Element {
  const [isOn, setIsOn] = useState(true);
  return (
    <table>
      <tbody>
        <tr>
          <td>
            {isOn ? (
              <ConfirmButton
                label="Turn off"
                choices={[
                  {
                    label: 'Turn it off',
                    onChoose: () => {
                      setIsOn(false);
                      return Promise.resolve();
                    },
                  },
                ]}
              />
            ) : (
              'Off'
            )}
          </td>
        </tr>
      </tbody>
    </table>
  );
}

function renderButton(onChoose: () => Promise<unknown>) {
  return renderWithProviders(
    <ConfirmButton label="Deactivate account" choices={[{ label: 'Go ahead', onChoose }]}>
      <p>They will be signed out.</p>
    </ConfirmButton>,
  );
}

describe('ConfirmButton', () => {
  it('shows only its button until it is pressed', () => {
    renderButton(vi.fn(() => Promise.resolve()));

    expect(screen.queryByText('They will be signed out.')).not.toBeInTheDocument();
  });

  it('draws its button small when asked, to sit among small buttons', () => {
    renderWithProviders(
      <ConfirmButton label="Clear batch" small choices={[]}>
        <p>Everybody goes.</p>
      </ConfirmButton>,
    );
    expect(screen.getByRole('button', { name: 'Clear batch' })).toHaveClass('button--small');
  });

  it('opens a panel naming the action, with the explanation', async () => {
    renderButton(vi.fn(() => Promise.resolve()));

    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));

    expect(screen.getByRole('region', { name: 'Deactivate account' })).toHaveTextContent(
      'They will be signed out.',
    );
  });

  it('acts only from the panel', async () => {
    const onChoose = vi.fn(() => Promise.resolve());
    renderButton(onChoose);

    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));
    await userEvent.click(screen.getByRole('button', { name: 'Go ahead' }));

    expect(onChoose).toHaveBeenCalledOnce();
  });

  it('closes once the choice has gone through', async () => {
    renderButton(vi.fn(() => Promise.resolve()));

    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));
    await userEvent.click(screen.getByRole('button', { name: 'Go ahead' }));

    await waitFor(() =>
      expect(screen.queryByRole('region', { name: 'Deactivate account' })).toBeNull(),
    );
  });

  it('gives the focus back to its button once the choice has gone through', async () => {
    renderButton(vi.fn(() => Promise.resolve()));

    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));
    await userEvent.click(screen.getByRole('button', { name: 'Go ahead' }));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Deactivate account' })).toHaveFocus(),
    );
  });

  it('gives the focus to its table cell when the choice takes the button away', async () => {
    renderWithProviders(<TurnOffRow />);

    await userEvent.click(screen.getByRole('button', { name: 'Turn off' }));
    await userEvent.click(screen.getByRole('button', { name: 'Turn it off' }));

    await waitFor(() => expect(screen.getByRole('cell', { name: 'Off' })).toHaveFocus());
  });

  it('stays in place while its panel is open, marked as expanded', async () => {
    renderButton(vi.fn(() => Promise.resolve()));

    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));

    expect(screen.getByRole('button', { name: 'Deactivate account' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
  });

  it('opens its panel on a line of its own below the row of buttons', async () => {
    renderButton(vi.fn(() => Promise.resolve()));

    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));

    expect(screen.getByRole('region', { name: 'Deactivate account' })).toHaveClass('confirm-panel');
  });

  it('closes its panel when its button is pressed again', async () => {
    renderButton(vi.fn(() => Promise.resolve()));

    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));
    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));

    expect(screen.queryByRole('region', { name: 'Deactivate account' })).toBeNull();
  });

  it('draws the panel buttons small when its own button is small', async () => {
    renderWithProviders(
      <ConfirmButton
        label="Turn off"
        small
        choices={[{ label: 'Turn it off', onChoose: vi.fn() }]}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Turn off' }));

    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveClass('button--small');
  });

  it('stays open when the choice is refused', async () => {
    renderButton(vi.fn(() => Promise.reject(new Error('refused'))));

    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));
    await userEvent.click(screen.getByRole('button', { name: 'Go ahead' }));

    expect(await screen.findByRole('button', { name: 'Go ahead' })).toBeEnabled();
  });

  it('closes on Cancel without acting', async () => {
    const onChoose = vi.fn(() => Promise.resolve());
    renderButton(onChoose);

    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onChoose).not.toHaveBeenCalled();
  });

  it('moves the focus to the first choice when it opens', async () => {
    renderButton(vi.fn(() => Promise.resolve()));

    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));

    expect(screen.getByRole('button', { name: 'Go ahead' })).toHaveFocus();
  });

  it('closes on Escape and gives the focus back to its button', async () => {
    const onChoose = vi.fn(() => Promise.resolve());
    renderButton(onChoose);

    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));
    await userEvent.keyboard('{Escape}');

    expect(screen.getByRole('button', { name: 'Deactivate account' })).toHaveFocus();
    expect(onChoose).not.toHaveBeenCalled();
  });

  it('gives the focus back to its button after Cancel', async () => {
    renderButton(vi.fn(() => Promise.resolve()));

    await userEvent.click(screen.getByRole('button', { name: 'Deactivate account' }));
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.getByRole('button', { name: 'Deactivate account' })).toHaveFocus();
  });
});
