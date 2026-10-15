import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@test/render';
import { Page } from './Page';

/** The eyebrow over the page title, or null when there isn't one. */
function eyebrow(container: HTMLElement): string | null {
  return container.querySelector('.page__header .eyebrow')?.textContent ?? null;
}

describe('<Page/>', () => {
  it.each([
    ['/leader', 'Operations'],
    ['/leader/aircraft', 'Operations'],
    ['/admin/payments/renewals', 'Finance'],
    ['/admin/users/4', 'Administration'],
    ['/messages', 'My account'],
    ['/bulk-email/sent', 'Bulk email'],
  ])('heads the page at %s with its menu group, %s', (route, group) => {
    const { container } = renderWithProviders(<Page title="Anything" />, { route });

    expect(eyebrow(container)).toBe(group);
  });

  it('leaves out the eyebrow for a page outside the menu', () => {
    const { container } = renderWithProviders(<Page title="Join CalDART" />, { route: '/join' });

    expect(eyebrow(container)).toBeNull();
  });

  it('leaves out the eyebrow when the page asks it to', () => {
    const { container } = renderWithProviders(<Page title="Page not found" noEyebrow />, {
      route: '/admin/members/999',
    });

    expect(eyebrow(container)).toBeNull();
  });

  it('names the browser tab after the page, then the organization', () => {
    renderWithProviders(<Page title="Member check" />, { route: '/leader' });

    expect(document.title).toBe('Member check · CalDART');
  });

  it('names the browser tab after the screen when the heading is a greeting', () => {
    renderWithProviders(<Page title="Welcome, Marta" tabTitle="Dashboard" />, { route: '/' });

    expect(document.title).toBe('Dashboard · CalDART');
  });

  it('puts the actions on the title line', () => {
    const { container } = renderWithProviders(
      <Page
        title="Members"
        lede="Everyone on file."
        actions={<button type="button">Add</button>}
      />,
      { route: '/admin/members' },
    );

    expect(container.querySelector('.page__heading')).toContainElement(
      screen.getByRole('button', { name: 'Add' }),
    );
  });

  it('leaves out the lede paragraph when there is not a lede', () => {
    const { container } = renderWithProviders(<Page title="Members" />, {
      route: '/admin/members',
    });

    expect(container.querySelector('.page__lede')).toBeNull();
  });
});
