import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import type { JSX } from 'react';
import { describe, expect, it, vi } from 'vitest';

import type { Option } from '@/portal/reports/types';
import { MultiSelect } from './MultiSelect';

const COUNTIES: Option[] = [
  { value: 'Alameda', label: 'Alameda' },
  { value: 'Marin', label: 'Marin' },
  { value: 'Napa', label: 'Napa' },
  { value: 'Santa Clara', label: 'Santa Clara' },
];

interface HarnessProps {
  initial?: string[];
  onChange?: (value: string[]) => void;
}

/** Holds the chosen values the way a filter bar does, reporting every change. */
function Harness({ initial = [], onChange: handleReport }: HarnessProps): JSX.Element {
  const [value, setValue] = useState(initial);
  const handleChange = (next: string[]): void => {
    setValue(next);
    handleReport?.(next);
  };
  return (
    <>
      <label htmlFor="county">County</label>
      <MultiSelect
        id="county"
        legend="County"
        options={COUNTIES}
        value={value}
        onChange={handleChange}
      />
      <p>somewhere else</p>
    </>
  );
}

describe('MultiSelect', () => {
  it('is a one-line box that reads Any while nothing is chosen', () => {
    render(<Harness />);

    expect(screen.getByLabelText('County')).toHaveTextContent('Any');
  });

  it('names the chosen options in the order they are listed', () => {
    render(<Harness initial={['Napa', 'Alameda']} />);

    expect(screen.getByLabelText('County')).toHaveTextContent('Alameda, Napa');
  });

  it('keeps its checkboxes shut until the box is pressed', () => {
    render(<Harness />);

    expect(screen.queryByRole('checkbox')).toBeNull();
  });

  it('opens a checkbox per option under the box when pressed', async () => {
    render(<Harness initial={['Marin']} />);

    await userEvent.click(screen.getByLabelText('County'));

    const boxes = screen.getAllByRole<HTMLInputElement>('checkbox');
    expect(boxes.map((box) => [box.value, box.checked])).toEqual([
      ['Alameda', false],
      ['Marin', true],
      ['Napa', false],
      ['Santa Clara', false],
    ]);
  });

  it('says whether the panel is open', async () => {
    render(<Harness />);

    await userEvent.click(screen.getByLabelText('County'));

    expect(screen.getByLabelText('County')).toHaveAttribute('aria-expanded', 'true');
  });

  it('sends the ticked values in list order and keeps the panel open', async () => {
    const handleChange = vi.fn();
    render(<Harness onChange={handleChange} />);

    await userEvent.click(screen.getByLabelText('County'));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Napa' }));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Alameda' }));

    expect(handleChange).toHaveBeenLastCalledWith(['Alameda', 'Napa']);
    expect(screen.getByRole('checkbox', { name: 'Napa' })).toBeChecked();
  });

  it('takes back the last choice when its checkbox is unticked', async () => {
    const handleChange = vi.fn();
    render(<Harness initial={['Marin']} onChange={handleChange} />);

    await userEvent.click(screen.getByLabelText('County'));
    await userEvent.click(screen.getByRole('checkbox', { name: 'Marin' }));

    expect(handleChange).toHaveBeenLastCalledWith([]);
  });

  it('takes back every choice at once with Clear', async () => {
    const handleChange = vi.fn();
    render(<Harness initial={['Marin', 'Napa']} onChange={handleChange} />);

    await userEvent.click(screen.getByLabelText('County'));
    await userEvent.click(screen.getByRole('button', { name: 'Clear' }));

    expect(handleChange).toHaveBeenLastCalledWith([]);
  });

  it('disables Clear while nothing is chosen', async () => {
    render(<Harness />);

    await userEvent.click(screen.getByLabelText('County'));

    expect(screen.getByRole('button', { name: 'Clear' })).toBeDisabled();
  });

  it('shuts the panel on a click outside it', async () => {
    render(<Harness />);

    await userEvent.click(screen.getByLabelText('County'));
    await userEvent.click(screen.getByText('somewhere else'));

    expect(screen.queryByRole('checkbox')).toBeNull();
  });

  it('shuts the panel on Escape and puts the focus back on the box', async () => {
    render(<Harness />);

    await userEvent.click(screen.getByLabelText('County'));
    await userEvent.tab();
    await userEvent.keyboard('{Escape}');

    expect(screen.queryByRole('checkbox')).toBeNull();
    expect(screen.getByLabelText('County')).toHaveFocus();
  });
});
