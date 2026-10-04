import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { renderRoutes } from '@test/render';
import { RouteError } from './route-error';

/** A route whose page cannot load, as when its code chunk fails to arrive. */
const BROKEN = [
  {
    path: '/',
    errorElement: <RouteError />,
    lazy: () => Promise.reject(new Error('Failed to fetch dynamically imported module')),
  },
];

describe('<RouteError/>', () => {
  it('says the page did not load instead of showing the developer error', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    renderRoutes(BROKEN);

    expect(
      await screen.findByRole('heading', { level: 1, name: 'This page did not load' }),
    ).toBeInTheDocument();
  });

  it('reloads the page from its Reload button', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const reload = vi.fn();
    vi.spyOn(window, 'location', 'get').mockReturnValue({ ...window.location, reload });
    renderRoutes(BROKEN);

    await userEvent.click(await screen.findByRole('button', { name: 'Reload' }));
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it('logs the error for whoever looks after the site', async () => {
    const logged = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    renderRoutes(BROKEN);

    await screen.findByRole('heading', { name: 'This page did not load' });
    expect(logged).toHaveBeenCalledWith(new Error('Failed to fetch dynamically imported module'));
  });
});
