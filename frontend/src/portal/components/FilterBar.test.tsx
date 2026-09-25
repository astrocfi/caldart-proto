import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import type { JSX } from 'react';
import { describe, expect, it, vi } from 'vitest';

import type { FilterField, FilterValues, Option } from '@/portal/reports/types';
import { FilterBar } from './FilterBar';

/** A change nobody needs to see. */
const handleNothing = (): void => {};

const FIELDS: FilterField[] = [
  { key: 'search', label: 'Search', kind: 'search', placeholder: 'Name or email' },
  {
    key: 'status',
    label: 'Status',
    kind: 'select',
    options: [
      { value: 'current', label: 'Current' },
      { value: 'expired', label: 'Expired' },
    ],
  },
  { key: 'plan', label: 'Plan', kind: 'select', placeholder: 'Any plan' },
  { key: 'within', label: 'Within (days)', kind: 'number' },
  { key: 'min_cents', label: 'At least', kind: 'number', isDollars: true },
  { key: 'from', label: 'From', kind: 'date' },
  { key: 'is_active', label: 'Active only', kind: 'toggle' },
  { key: 'period', label: 'Period', kind: 'select', subscriptionOnly: true, options: [] },
];

interface HarnessProps {
  initial?: FilterValues;
  onChange: (values: FilterValues) => void;
  fields?: FilterField[];
  options?: Record<string, Option[]>;
}

/** Holds the values the way a list page does, reporting every change to `onChange`. */
function Harness({
  initial = {},
  onChange: handleReport,
  fields = FIELDS,
  options,
}: HarnessProps): JSX.Element {
  const [values, setValues] = useState<FilterValues>(initial);
  const handleChange = (next: FilterValues): void => {
    setValues(next);
    handleReport(next);
  };
  return <FilterBar fields={fields} values={values} onChange={handleChange} options={options} />;
}

describe('FilterBar', () => {
  it('applies a search once the typing pauses, not per keystroke', async () => {
    const handleChange = vi.fn();
    render(<Harness onChange={handleChange} />);

    await userEvent.type(screen.getByLabelText('Search'), 'dana');

    await waitFor(() => expect(handleChange).toHaveBeenCalledTimes(1));
    expect(handleChange).toHaveBeenLastCalledWith(expect.objectContaining({ search: 'dana' }));
  });

  it('shows a search field as a search box with its placeholder', () => {
    render(<Harness onChange={handleNothing} />);

    expect(screen.getByRole('searchbox', { name: 'Search' })).toHaveAttribute(
      'placeholder',
      'Name or email',
    );
  });

  it('applies a select as soon as it changes', async () => {
    const handleChange = vi.fn();
    render(<Harness onChange={handleChange} />);

    await userEvent.selectOptions(screen.getByLabelText('Status'), 'expired');

    expect(handleChange).toHaveBeenCalledWith(expect.objectContaining({ status: 'expired' }));
  });

  it('opens a select on a blank "Any" option', () => {
    render(<Harness onChange={handleNothing} />);

    const first = screen.getByLabelText<HTMLSelectElement>('Status').options[0];
    expect([first?.value, first?.textContent]).toEqual(['', 'Any']);
  });

  it('names the blank option after the placeholder when a field gives one', () => {
    render(<Harness onChange={handleNothing} />);

    expect(screen.getByLabelText<HTMLSelectElement>('Plan').options[0]?.textContent).toBe(
      'Any plan',
    );
  });

  it('takes a select field’s choices from the options prop', () => {
    render(
      <Harness
        onChange={handleNothing}
        options={{ plan: [{ value: 'annual', label: 'Annual' }] }}
      />,
    );

    expect(screen.getByRole('option', { name: 'Annual' })).toHaveValue('annual');
  });

  it('lets the options prop replace a field’s own choices', () => {
    render(
      <Harness onChange={handleNothing} options={{ status: [{ value: 'new', label: 'New' }] }} />,
    );

    expect(screen.queryByRole('option', { name: 'Current' })).not.toBeInTheDocument();
  });

  it('keeps only digits in a number field', async () => {
    const handleChange = vi.fn();
    render(<Harness onChange={handleChange} />);

    await userEvent.type(screen.getByLabelText('Within (days)'), '3x0');

    await waitFor(() =>
      expect(handleChange).toHaveBeenLastCalledWith(expect.objectContaining({ within: '30' })),
    );
  });

  it('sends whole dollars typed in a dollar field as cents', async () => {
    const handleChange = vi.fn();
    render(<Harness onChange={handleChange} />);

    await userEvent.type(screen.getByLabelText('At least'), '50');

    await waitFor(() =>
      expect(handleChange).toHaveBeenLastCalledWith(expect.objectContaining({ min_cents: '5000' })),
    );
  });

  it('shows cents in a dollar field as dollars', () => {
    render(<Harness initial={{ min_cents: '2500' }} onChange={handleNothing} />);

    expect(screen.getByLabelText('At least')).toHaveValue('25');
  });

  it('applies a date as soon as it is picked', async () => {
    const handleChange = vi.fn();
    render(<Harness onChange={handleChange} />);

    await userEvent.type(screen.getByLabelText('From'), '2026-01-31');

    expect(handleChange).toHaveBeenLastCalledWith(expect.objectContaining({ from: '2026-01-31' }));
  });

  it('sends true for a ticked toggle', async () => {
    const handleChange = vi.fn();
    render(<Harness onChange={handleChange} />);

    await userEvent.click(screen.getByRole('checkbox', { name: 'Active only' }));

    expect(handleChange).toHaveBeenLastCalledWith(expect.objectContaining({ is_active: 'true' }));
  });

  it('sends nothing for a toggle ticked off again', async () => {
    const handleChange = vi.fn();
    render(<Harness initial={{ is_active: 'true' }} onChange={handleChange} />);

    await userEvent.click(screen.getByRole('checkbox', { name: 'Active only' }));

    expect(handleChange).toHaveBeenLastCalledWith(expect.objectContaining({ is_active: '' }));
  });

  it('empties every value on Clear', async () => {
    const handleChange = vi.fn();
    render(
      <Harness
        initial={{ search: 'dana', status: 'current', from: '2026-01-01', is_active: 'true' }}
        onChange={handleChange}
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'Clear' }));

    expect(handleChange).toHaveBeenLastCalledWith(
      Object.fromEntries(FIELDS.map((field) => [field.key, ''])),
    );
  });

  it('empties the typed boxes on Clear', async () => {
    render(<Harness initial={{ search: 'dana' }} onChange={handleNothing} />);

    await userEvent.click(screen.getByRole('button', { name: 'Clear' }));

    expect(screen.getByLabelText('Search')).toHaveValue('');
  });

  it('does not put back a search that was still settling when Clear was pressed', async () => {
    const handleChange = vi.fn();
    render(<Harness onChange={handleChange} />);

    await userEvent.type(screen.getByLabelText('Search'), 'dana');
    await userEvent.click(screen.getByRole('button', { name: 'Clear' }));
    await new Promise((resolve) => setTimeout(resolve, 400));

    expect(handleChange).toHaveBeenLastCalledWith(expect.objectContaining({ search: '' }));
  });

  it('keeps what is being typed when the page re-renders with the same values', async () => {
    const handleChange = vi.fn();
    const { rerender } = render(
      <FilterBar fields={FIELDS} values={{ search: '' }} onChange={handleChange} />,
    );

    await userEvent.type(screen.getByLabelText('Search'), 'da');
    rerender(<FilterBar fields={FIELDS} values={{ search: '' }} onChange={handleChange} />);

    expect(screen.getByLabelText('Search')).toHaveValue('da');
  });

  it('follows values changed from outside, such as the back button', () => {
    const { rerender } = render(
      <FilterBar fields={FIELDS} values={{ search: 'dana' }} onChange={handleNothing} />,
    );

    rerender(<FilterBar fields={FIELDS} values={{ search: 'lee' }} onChange={handleNothing} />);

    expect(screen.getByLabelText('Search')).toHaveValue('lee');
  });

  it('is one search landmark named by its label', () => {
    render(
      <FilterBar fields={FIELDS} values={{}} onChange={handleNothing} label="Filter members" />,
    );

    expect(screen.getByRole('search', { name: 'Filter members' })).toBeInTheDocument();
  });

  it('shows a field’s hint under it', () => {
    render(
      <FilterBar
        fields={[{ key: 'make', label: 'Make', kind: 'search', hint: 'Cessna, Piper, …' }]}
        values={{}}
        onChange={handleNothing}
      />,
    );

    expect(screen.getByLabelText('Make')).toHaveAccessibleDescription('Cessna, Piper, …');
  });

  it('sends a settled search once even when the page does not adopt it', async () => {
    const handleChange = vi.fn<(values: FilterValues) => void>();
    const { rerender } = render(<FilterBar fields={FIELDS} values={{}} onChange={handleChange} />);

    await userEvent.type(screen.getByLabelText('Search'), 'dana');
    await waitFor(() => expect(handleChange).toHaveBeenCalledTimes(1));
    rerender(<FilterBar fields={FIELDS} values={{}} onChange={(next) => handleChange(next)} />);
    await new Promise((resolve) => setTimeout(resolve, 400));

    expect(handleChange).toHaveBeenCalledTimes(1);
  });

  it('applies a lone box at once when Enter is pressed', async () => {
    const handleChange = vi.fn();
    render(
      <Harness
        fields={[{ key: 'within', label: 'Within (days)', kind: 'number' }]}
        onChange={handleChange}
      />,
    );

    await userEvent.type(screen.getByLabelText('Within (days)'), '45{Enter}');

    expect(handleChange).toHaveBeenCalledWith({ within: '45' });
  });
});
