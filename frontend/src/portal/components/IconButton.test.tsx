import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { IconButton } from './IconButton';

describe('IconButton', () => {
  it('takes its accessible name from the label', () => {
    render(<IconButton icon="trashcan" label="Remove N12345" />);

    expect(screen.getByRole('button', { name: 'Remove N12345' })).toBeInTheDocument();
  });

  it('carries the label as a tooltip so the icon can be identified by pointer', () => {
    render(<IconButton icon="arrow-up" label="Move person 1 up" />);

    expect(screen.getByRole('button', { name: 'Move person 1 up' })).toHaveAttribute(
      'title',
      'Move person 1 up',
    );
  });

  it('keeps a caller-supplied title, such as the reason it is disabled', () => {
    render(<IconButton icon="arrow-up" label="Move person 1 up" title="Already first" disabled />);

    expect(screen.getByRole('button', { name: 'Move person 1 up' })).toHaveAttribute(
      'title',
      'Already first',
    );
  });

  it('is a bare icon button rather than one of the portal button variants', () => {
    render(<IconButton icon="trashcan" label="Remove N12345" />);

    const button = screen.getByRole('button', { name: 'Remove N12345' });
    expect(button).toHaveClass('icon-button');
  });

  it('carries none of the portal button classes', () => {
    render(<IconButton icon="trashcan" label="Remove N12345" />);

    expect(screen.getByRole('button', { name: 'Remove N12345' })).not.toHaveClass('button');
  });

  it('keeps a caller-supplied class beside its own', () => {
    render(<IconButton icon="trashcan" label="Remove N12345" className="contact-row__move" />);

    expect(screen.getByRole('button', { name: 'Remove N12345' })).toHaveClass('contact-row__move');
  });

  it('draws its icon where a screen reader will not announce it', () => {
    const { container } = render(<IconButton icon="arrow-down" label="Move person 1 down" />);

    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  it('shows one icon and no words', () => {
    render(<IconButton icon="trashcan" label="Remove N12345" />);

    expect(screen.getByRole('button', { name: 'Remove N12345' }).textContent).toBe('');
  });

  it('draws a different path for each icon it offers', () => {
    const up = render(<IconButton icon="arrow-up" label="Move person 1 up" />);
    const down = render(<IconButton icon="arrow-down" label="Move person 1 down" />);

    expect(up.container.querySelector('svg')?.innerHTML).not.toBe(
      down.container.querySelector('svg')?.innerHTML,
    );
  });

  it('reports the press to the caller', async () => {
    const handleMove = vi.fn();
    render(<IconButton icon="arrow-up" label="Move person 1 up" onClick={handleMove} />);

    await userEvent.click(screen.getByRole('button', { name: 'Move person 1 up' }));

    expect(handleMove).toHaveBeenCalledOnce();
  });

  it('ignores a press while it is disabled', async () => {
    const handleMove = vi.fn();
    render(<IconButton icon="arrow-up" label="Move person 1 up" disabled onClick={handleMove} />);

    await userEvent.click(screen.getByRole('button', { name: 'Move person 1 up' }));

    expect(handleMove).not.toHaveBeenCalled();
  });

  it('does not submit the form it sits in', () => {
    render(<IconButton icon="trashcan" label="Remove person 1" />);

    expect(screen.getByRole('button', { name: 'Remove person 1' })).toHaveAttribute(
      'type',
      'button',
    );
  });
});
