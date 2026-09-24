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

  it('marks itself as an icon-only button when it shows no text', () => {
    render(<DeleteButton label="Remove N12345" />);

    expect(screen.getByRole('button', { name: 'Remove N12345' })).toHaveClass('button--icon');
  });

  it('draws the trashcan where a screen reader will not announce it', () => {
    const { container } = render(<DeleteButton label="Remove N12345" />);

    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  it('reads as its text rather than its label when it shows text', () => {
    render(<DeleteButton label="Delete this DART">Delete this DART</DeleteButton>);

    expect(screen.getByRole('button', { name: 'Delete this DART' })).not.toHaveAttribute(
      'aria-label',
    );
  });

  it('is not an icon-only button when it shows text', () => {
    render(<DeleteButton label="Delete this DART">Delete this DART</DeleteButton>);

    expect(screen.getByRole('button', { name: 'Delete this DART' })).not.toHaveClass(
      'button--icon',
    );
  });

  it('is quiet and small unless the caller says otherwise', () => {
    render(<DeleteButton label="Remove person 1" />);

    expect(screen.getByRole('button', { name: 'Remove person 1' })).toHaveClass('button--quiet');
  });

  it('takes the danger variant when the caller asks for it', () => {
    render(
      <DeleteButton label="Delete member" variant="danger">
        Delete member
      </DeleteButton>,
    );

    expect(screen.getByRole('button', { name: 'Delete member' })).toHaveClass('button--danger');
  });

  it('reports the press to the caller', async () => {
    const handleDelete = vi.fn();
    render(<DeleteButton label="Remove N12345" onClick={handleDelete} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));

    expect(handleDelete).toHaveBeenCalledOnce();
  });

  it('ignores a press while it is disabled', async () => {
    const handleDelete = vi.fn();
    render(<DeleteButton label="Remove N12345" disabled onClick={handleDelete} />);

    await userEvent.click(screen.getByRole('button', { name: 'Remove N12345' }));

    expect(handleDelete).not.toHaveBeenCalled();
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
