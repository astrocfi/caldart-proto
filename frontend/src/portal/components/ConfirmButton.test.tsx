import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@test/render';
import { ConfirmButton } from './ConfirmButton';

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

    expect(await screen.findByRole('button', { name: 'Deactivate account' })).toBeInTheDocument();
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
});
