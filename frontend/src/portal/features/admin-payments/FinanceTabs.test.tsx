import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AUTH_ME_KEY } from '@/portal/auth/useAuth';
import { makeUser, signedInAs } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
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
  it('shows every screen in the finance area to a treasurer', async () => {
    server.use(signedInAs(makeUser({ roles: ['treasurer'] })));
    const result = renderWithProviders(<FinanceTabs />, { route: '/admin/payments' });
    await waitFor(() => expect(result.client.getQueryState(AUTH_ME_KEY)?.status).toBe('success'));

    expect(await screen.findAllByRole('link')).toHaveLength(FINANCE_TABS.length);
  });

  it('hides the treasurer-only Donors tab from an account administrator', async () => {
    server.use(signedInAs(makeUser({ roles: ['account_admin'] })));
    const result = renderWithProviders(<FinanceTabs />, { route: '/admin/payments' });
    await waitFor(() => expect(result.client.getQueryState(AUTH_ME_KEY)?.status).toBe('success'));

    await screen.findByRole('link', { name: 'Overview' });
    expect(screen.queryByRole('link', { name: 'Donors' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('link')).toHaveLength(FINANCE_TABS.length - 1);
  });

  it('shows the Donors tab to a system administrator', async () => {
    server.use(signedInAs(makeUser({ roles: ['system_admin'] })));
    const result = renderWithProviders(<FinanceTabs />, { route: '/admin/payments' });
    await waitFor(() => expect(result.client.getQueryState(AUTH_ME_KEY)?.status).toBe('success'));

    expect(await screen.findByRole('link', { name: 'Donors' })).toBeInTheDocument();
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
