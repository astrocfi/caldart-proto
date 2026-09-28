import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { Plan } from '@/portal/api/types';
import { FRIEND_CHOICE, PlanChooser } from './PlanChooser';

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

const FRIEND_HEADING = 'I changed my mind, I just want to be a friend';

describe('<PlanChooser/>', () => {
  it('offers the plans alone unless asked to offer a friend', () => {
    render(<PlanChooser plans={PLANS} value="annual" onChange={() => {}} />);

    expect(screen.getAllByRole('radio')).toHaveLength(2);
  });

  it('adds a friend card after the plans when asked', () => {
    render(<PlanChooser plans={PLANS} value="annual" onChange={() => {}} offerFriend />);

    const radios = screen.getAllByRole('radio');
    expect(radios.at(-1)).toHaveAccessibleName(expect.stringContaining(FRIEND_HEADING));
  });

  it('says what a friend is on the friend card', () => {
    render(<PlanChooser plans={PLANS} value="annual" onChange={() => {}} offerFriend />);

    expect(
      screen.getByText('A friend has an account and hears from CalDART, but is not a member.'),
    ).toBeInTheDocument();
  });

  it('reports the friend choice by its own value', async () => {
    const handleChange = vi.fn();
    render(<PlanChooser plans={PLANS} value="annual" onChange={handleChange} offerFriend />);

    await userEvent.click(screen.getByRole('radio', { name: new RegExp(FRIEND_HEADING) }));

    expect(handleChange).toHaveBeenCalledWith(FRIEND_CHOICE);
  });

  it('marks the friend card as chosen when it is the value', () => {
    render(<PlanChooser plans={PLANS} value={FRIEND_CHOICE} onChange={() => {}} offerFriend />);

    expect(screen.getByRole('radio', { name: new RegExp(FRIEND_HEADING) })).toBeChecked();
  });
});
