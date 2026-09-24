import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@test/render';
import { FINANCE_TABS, FinanceTabs, isTabCurrent } from './FinanceTabs';

describe('isTabCurrent', () => {
  it('matches an exact tab only on its own path', () => {
    expect(
      isTabCurrent({ to: '/admin/payments', label: 'Overview', end: true }, '/admin/payments'),
    ).toBe(true);
  });

  it('does not claim a nested path for an exact tab', () => {
    expect(
      isTabCurrent({ to: '/admin/payments', label: 'Overview', end: true }, '/admin/payments/412'),
    ).toBe(false);
  });

  it('claims a nested path for a prefix tab', () => {
    expect(
      isTabCurrent({ to: '/admin/payments/list', label: 'Payments' }, '/admin/payments/list'),
    ).toBe(true);
  });
});

describe('FinanceTabs', () => {
  it('shows every screen in the finance area', () => {
    renderWithProviders(<FinanceTabs />, { route: '/admin/payments' });

    expect(screen.getAllByRole('link')).toHaveLength(FINANCE_TABS.length);
  });

  it('marks the tab the reader is standing on', () => {
    renderWithProviders(<FinanceTabs />, { route: '/admin/payments/list' });

    expect(screen.getByRole('link', { name: 'Payments' })).toHaveAttribute('aria-current', 'page');
  });

  it('marks the named tab for a screen that hangs off one', () => {
    renderWithProviders(<FinanceTabs current="/admin/payments/list" />, {
      route: '/admin/payments/412',
    });

    expect(screen.getByRole('link', { name: 'Payments' })).toHaveAttribute('aria-current', 'page');
  });

  it('leaves the overview unmarked on a detail screen', () => {
    renderWithProviders(<FinanceTabs current="/admin/payments/list" />, {
      route: '/admin/payments/412',
    });

    expect(screen.getByRole('link', { name: 'Overview' })).not.toHaveAttribute('aria-current');
  });
});
