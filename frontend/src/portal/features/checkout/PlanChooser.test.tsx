import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { Plan } from '@/portal/api/types';
import { PlanChooser } from './PlanChooser';

const PLANS: Plan[] = [
  {
    slug: 'annual',
    name: 'Annual',
    price_cents: 4500,
    duration_days: 365,
    description: '',
  },
  {
    slug: 'life',
    name: 'Life',
    price_cents: 65000,
    duration_days: null,
    description: '',
  },
];

describe('<PlanChooser/>', () => {
  it('offers each plan as a card to choose', () => {
    render(<PlanChooser plans={PLANS} value="annual" onChange={() => {}} />);

    expect(screen.getAllByRole('radio')).toHaveLength(2);
  });

  it('reports the plan chosen', async () => {
    const handleChange = vi.fn();
    render(<PlanChooser plans={PLANS} value="annual" onChange={handleChange} />);

    await userEvent.click(screen.getByRole('radio', { name: /Life/ }));

    expect(handleChange).toHaveBeenCalledWith('life');
  });

  it('names a single plan in plain text rather than as a choice of one', () => {
    render(<PlanChooser plans={PLANS.slice(0, 1)} value="annual" onChange={() => {}} />);

    expect(screen.queryByRole('radio')).not.toBeInTheDocument();
    expect(screen.getByText('Annual')).toBeInTheDocument();
    expect(screen.getByText('$45.00')).toBeInTheDocument();
    expect(screen.getByText('One year')).toBeInTheDocument();
  });
});
