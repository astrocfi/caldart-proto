import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { DeleteButton } from './DeleteButton';

describe('DeleteButton', () => {
  it('takes its accessible name from the label when it shows no text', () => {
    render(<DeleteButton label="Remove N12345" />);

    expect(screen.getByRole('button', { name: 'Remove N12345' })).toBeInTheDocument();
  });

  it('carries the label as a tooltip so the icon can be identified by pointer', () => {
    render(<DeleteButton label="Remove N12345" />);

    expect(screen.getByRole('button', { name: 'Remove N12345' })).toHaveAttribute(
      'title',
      'Remove N12345',
    );
  });

  it('is a bare icon button when it shows no text', () => {
    render(<DeleteButton label="Remove N12345" />);

    expect(screen.getByRole('button', { name: 'Remove N12345' })).toHaveClass('icon-button');
  });

  it('carries none of the portal button classes when it shows no text', () => {
    render(<DeleteButton label="Remove N12345" />);

    expect(screen.getByRole('button', { name: 'Remove N12345' })).not.toHaveClass('button');
  });

  it('draws the trashcan where a screen reader will not announce it', () => {
    const { container } = render(<DeleteButton label="Remove N12345" />);

    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  it('draws the trashcan rather than another icon when it shows no text', () => {
    const { container } = render(<DeleteButton label="Remove N12345" />);

    expect(container.querySelector('svg path[d="M4 7h16"]')).toBeInTheDocument();
  });

  it('reads as its text rather than its label when it shows text', () => {
    render(<DeleteButton label="Delete this DART">Delete this DART</DeleteButton>);

    expect(screen.getByRole('button', { name: 'Delete this DART' })).not.toHaveAttribute(
      'aria-label',
    );
  });

  it('shows no tooltip when it already shows its words', () => {
    render(<DeleteButton label="Delete member">Delete member</DeleteButton>);

    expect(screen.getByRole('button', { name: 'Delete member' })).not.toHaveAttribute('title');
  });

  it('is still named by its label when the words it would show are withheld', () => {
    render(<DeleteButton label="Remove N12345">{false}</DeleteButton>);

    expect(screen.getByRole('button', { name: 'Remove N12345' })).toHaveClass('icon-button');
  });

  it('is a portal button rather than a bare icon when it shows text', () => {
    render(<DeleteButton label="Delete this DART">Delete this DART</DeleteButton>);

    expect(screen.getByRole('button', { name: 'Delete this DART' })).not.toHaveClass('icon-button');
  });

  it('is quiet unless the caller asks for another variant', () => {
    render(<DeleteButton label="Delete member">Delete member</DeleteButton>);

    expect(screen.getByRole('button', { name: 'Delete member' })).toHaveClass('button--quiet');
  });

  it('is small unless the caller asks for a full-size button', () => {
    render(<DeleteButton label="Delete member">Delete member</DeleteButton>);

    expect(screen.getByRole('button', { name: 'Delete member' })).toHaveClass('button--small');
  });

  it('draws the trashcan at the text size when it shows words', () => {
    const { container } = render(<DeleteButton label="Delete member">Delete member</DeleteButton>);

    expect(container.querySelector('svg')).toHaveAttribute('width', '1em');
  });

  it('draws the trashcan at the shared icon size when it shows no text', () => {
    const { container } = render(<DeleteButton label="Remove N12345" />);

    expect(container.querySelector('svg')).toHaveAttribute('width', '1.25em');
  });

  it('takes the danger variant when the caller asks for it', () => {
    render(
      <DeleteButton label="Delete member" variant="danger">
        Delete member
      </DeleteButton>,
    );

    expect(screen.getByRole('button', { name: 'Delete member' })).toHaveClass('button--danger');
  });

  it('reports the press to the caller when it has no confirmation of its own', async () => {
    const handleClick = vi.fn();
    render(<DeleteButton label="Remove N12345" onClick={handleClick} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));

    expect(handleClick).toHaveBeenCalledOnce();
  });

  it('ignores a press while it is disabled', async () => {
    const handleClick = vi.fn();
    render(<DeleteButton label="Remove N12345" disabled onClick={handleClick} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));

    expect(handleClick).not.toHaveBeenCalled();
  });

  it('keeps a caller-supplied title, such as the reason it is disabled', () => {
    render(<DeleteButton label="Delete this DART" title="3 members are attached" disabled />);

    expect(screen.getByRole('button', { name: 'Delete this DART' })).toHaveAttribute(
      'title',
      '3 members are attached',
    );
  });

  it('does not submit the form it sits in unless it is asked to', () => {
    render(<DeleteButton label="Remove person 1" />);

    expect(screen.getByRole('button', { name: 'Remove person 1' })).toHaveAttribute(
      'type',
      'button',
    );
  });
});

describe('DeleteButton confirmation', () => {
  it('does not call onDelete on the first press', async () => {
    const handleDelete = vi.fn();
    render(<DeleteButton label="Remove N12345" onDelete={handleDelete} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));

    expect(handleDelete).not.toHaveBeenCalled();
  });

  it('replaces the trashcan with a named confirmation group on the first press', async () => {
    render(<DeleteButton label="Remove N12345" onDelete={() => {}} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));

    expect(screen.queryByRole('button', { name: 'Remove N12345' })).toBeNull();
    expect(screen.getByRole('group', { name: 'Remove N12345' })).toBeInTheDocument();
  });

  it('reads Delete on the confirmation unless the caller names another word', async () => {
    render(<DeleteButton label="Remove N12345" onDelete={() => {}} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));

    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
  });

  it('reads the caller-chosen word on the confirmation', async () => {
    render(<DeleteButton label="Remove N12345" confirmLabel="Remove" onDelete={() => {}} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));

    expect(screen.getByRole('button', { name: 'Remove' })).toBeInTheDocument();
  });

  it('calls onDelete only once the confirmation is pressed', async () => {
    const handleDelete = vi.fn().mockResolvedValue(undefined);
    render(<DeleteButton label="Remove N12345" onDelete={handleDelete} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));

    expect(handleDelete).toHaveBeenCalledOnce();
  });

  it('restores the trashcan once onDelete settles', async () => {
    const handleDelete = vi.fn().mockResolvedValue(undefined);
    render(<DeleteButton label="Remove N12345" onDelete={handleDelete} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));

    expect(await screen.findByRole('button', { name: 'Remove N12345' })).toBeInTheDocument();
  });

  it('restores the trashcan even when onDelete fails', async () => {
    const handleDelete = vi.fn().mockRejectedValue(new Error('nope'));
    render(<DeleteButton label="Remove N12345" onDelete={handleDelete} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));

    expect(await screen.findByRole('button', { name: 'Remove N12345' })).toBeInTheDocument();
  });

  it('disables both confirmation buttons while onDelete is in flight', async () => {
    let resolveDelete: () => void = () => {};
    const handleDelete = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveDelete = resolve;
        }),
    );
    render(<DeleteButton label="Remove N12345" onDelete={handleDelete} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));

    expect(screen.getByRole('button', { name: 'Delete' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Keep' })).toBeDisabled();

    resolveDelete();
    await screen.findByRole('button', { name: 'Remove N12345' });
  });

  it('restores the trashcan when Keep is pressed, without calling onDelete', async () => {
    const handleDelete = vi.fn();
    render(<DeleteButton label="Remove N12345" onDelete={handleDelete} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));
    await userEvent.click(screen.getByRole('button', { name: 'Keep' }));

    expect(screen.getByRole('button', { name: 'Remove N12345' })).toBeInTheDocument();
    expect(handleDelete).not.toHaveBeenCalled();
  });

  it('restores the trashcan on Escape, without calling onDelete', async () => {
    const handleDelete = vi.fn();
    render(<DeleteButton label="Remove N12345" onDelete={handleDelete} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));
    await userEvent.keyboard('{Escape}');

    expect(screen.getByRole('button', { name: 'Remove N12345' })).toBeInTheDocument();
    expect(handleDelete).not.toHaveBeenCalled();
  });

  it('moves the focus to Keep when the confirmation opens', async () => {
    render(<DeleteButton label="Remove N12345" onDelete={() => {}} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));

    expect(screen.getByRole('button', { name: 'Keep' })).toHaveFocus();
  });

  it('hands the focus back to the trashcan on Keep', async () => {
    render(<DeleteButton label="Remove N12345" onDelete={() => {}} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));
    await userEvent.click(screen.getByRole('button', { name: 'Keep' }));

    expect(screen.getByRole('button', { name: 'Remove N12345' })).toHaveFocus();
  });

  it('hands the focus back to the trashcan on Escape', async () => {
    render(<DeleteButton label="Remove N12345" onDelete={() => {}} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));
    await userEvent.keyboard('{Escape}');

    expect(screen.getByRole('button', { name: 'Remove N12345' })).toHaveFocus();
  });

  it('keeps an Escape pressed on the confirmation from reaching the page around it', async () => {
    const handlePageKey = vi.fn();
    document.addEventListener('keydown', handlePageKey);
    try {
      render(<DeleteButton label="Remove N12345" onDelete={() => {}} />);

      await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));
      await userEvent.keyboard('{Escape}');

      expect(handlePageKey).not.toHaveBeenCalled();
    } finally {
      document.removeEventListener('keydown', handlePageKey);
    }
  });

  it('restores the trashcan on a press outside it, without calling onDelete', async () => {
    const handleDelete = vi.fn();
    render(
      <>
        <DeleteButton label="Remove N12345" onDelete={handleDelete} />
        <p>somewhere else</p>
      </>,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));
    await userEvent.click(screen.getByText('somewhere else'));

    expect(screen.getByRole('button', { name: 'Remove N12345' })).toBeInTheDocument();
    expect(handleDelete).not.toHaveBeenCalled();
  });

  it('restores the trashcan when the focus leaves it, without calling onDelete', async () => {
    const handleDelete = vi.fn();
    render(
      <>
        <DeleteButton label="Remove N12345" onDelete={handleDelete} />
        <button>elsewhere</button>
      </>,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));
    screen.getByRole('button', { name: 'Keep' }).focus();
    await userEvent.tab();

    expect(screen.getByRole('button', { name: 'Remove N12345' })).toBeInTheDocument();
    expect(handleDelete).not.toHaveBeenCalled();
  });

  it('confirms in the worded form too', async () => {
    const handleDelete = vi.fn();
    render(
      <DeleteButton label="Delete this DART" confirmLabel="Delete for good" onDelete={handleDelete}>
        Delete this DART
      </DeleteButton>,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Delete this DART' }));

    expect(screen.getByRole('group', { name: 'Delete this DART' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete for good' })).toBeInTheDocument();
    expect(handleDelete).not.toHaveBeenCalled();
  });

  it('never shows a confirmation for a caller with no onDelete', async () => {
    const handleClick = vi.fn();
    render(<DeleteButton label="Delete member" type="submit" onClick={handleClick} />);

    await userEvent.click(screen.getByRole('button', { name: 'Delete member' }));

    expect(screen.queryByRole('group', { name: 'Delete member' })).toBeNull();
    expect(handleClick).toHaveBeenCalledOnce();
  });
});
