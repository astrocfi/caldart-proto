import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse, http } from 'msw';
import { describe, expect, it } from 'vitest';

import { API, makeAdminUser } from '@test/handlers';
import { renderWithProviders } from '@test/render';
import { server } from '@test/server';
import { SYSTEM_ADMIN_ONLY, TwoFactorCard } from './TwoFactorCard';

describe('<TwoFactorCard/>', () => {
  it('says two-factor sign-in is on', () => {
    renderWithProviders(
      <TwoFactorCard user={makeAdminUser({ two_factor_enabled: true })} isSelf={false} />,
    );
    expect(screen.getByText('On')).toBeInTheDocument();
  });

  it('says two-factor sign-in is off', () => {
    renderWithProviders(<TwoFactorCard user={makeAdminUser()} isSelf={false} />);
    expect(screen.getByText('Off')).toBeInTheDocument();
  });

  it("doesn't offer a reset while two-factor sign-in is off", () => {
    renderWithProviders(<TwoFactorCard user={makeAdminUser()} isSelf={false} />);
    expect(screen.queryByRole('button', { name: 'Reset two-factor' })).not.toBeInTheDocument();
  });

  it('grays the reset out when the server says the caller may not reset it', () => {
    const target = makeAdminUser({ two_factor_enabled: true, can_reset_two_factor: false });
    renderWithProviders(<TwoFactorCard user={target} isSelf={false} />);
    expect(screen.getByText(SYSTEM_ADMIN_ONLY)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reset two-factor' })).toBeDisabled();
  });

  it("doesn't offer a reset on your own record", () => {
    renderWithProviders(
      <TwoFactorCard user={makeAdminUser({ two_factor_enabled: true })} isSelf />,
    );
    expect(screen.queryByRole('button', { name: 'Reset two-factor' })).not.toBeInTheDocument();
  });

  it('asks first, then posts the reset', async () => {
    const user = makeAdminUser({ id: 41, two_factor_enabled: true });
    let posted = false;
    server.use(
      http.post(`${API}/admin/users/41/reset-two-factor`, () => {
        posted = true;
        return HttpResponse.json({ ...user, two_factor_enabled: false });
      }),
    );
    renderWithProviders(<TwoFactorCard user={user} isSelf={false} />);
    await userEvent.click(screen.getByRole('button', { name: 'Reset two-factor' }));
    expect(posted).toBe(false);
    await userEvent.click(
      within(screen.getByRole('region', { name: 'Reset two-factor' })).getByRole('button', {
        name: 'Yes, reset two-factor',
      }),
    );

    await waitFor(() => expect(posted).toBe(true));
  });

  it('shows why a reset was refused', async () => {
    const user = makeAdminUser({ id: 42, two_factor_enabled: true });
    server.use(
      http.post(`${API}/admin/users/42/reset-two-factor`, () =>
        HttpResponse.json({ detail: 'You cannot reset that account.' }, { status: 400 }),
      ),
    );
    renderWithProviders(<TwoFactorCard user={user} isSelf={false} />);
    await userEvent.click(screen.getByRole('button', { name: 'Reset two-factor' }));
    await userEvent.click(
      within(screen.getByRole('region', { name: 'Reset two-factor' })).getByRole('button', {
        name: 'Yes, reset two-factor',
      }),
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('You cannot reset that account.');
  });
});
