/** The frame every sign-in, password, and email screen renders through. */
import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@test/render';
import { AuthShell } from './AuthShell';

describe('AuthShell', () => {
  it('names the screen in its only top-level heading', () => {
    renderWithProviders(
      <AuthShell title="Sign in">
        <p>form</p>
      </AuthShell>,
    );

    expect(screen.getByRole('heading', { level: 1, name: 'Sign in' })).toHaveClass('auth__title');
  });

  it('puts its content inside one auth card', () => {
    const { container } = renderWithProviders(
      <AuthShell title="Sign in">
        <p>the form</p>
      </AuthShell>,
    );

    const card = container.querySelector('section.card.auth-card');
    expect(card).not.toBeNull();
    expect(within(card as HTMLElement).getByText('the form')).toBeInTheDocument();
  });

  it('shows the lede under the title', () => {
    renderWithProviders(
      <AuthShell title="Sign in" lede="Use the email address CalDART has on file.">
        <p>form</p>
      </AuthShell>,
    );

    expect(screen.getByText('Use the email address CalDART has on file.')).toHaveClass(
      'auth__lede',
    );
  });

  it('shows the footer below the card, outside it', () => {
    const { container } = renderWithProviders(
      <AuthShell title="Sign in" footer="Not a member yet?">
        <p>form</p>
      </AuthShell>,
    );

    const footer = screen.getByText('Not a member yet?');
    expect(footer).toHaveClass('auth__footer');
    expect(container.querySelector('.auth-card')).not.toContainElement(footer);
  });

  it('leaves out the lede and footer when none is given', () => {
    const { container } = renderWithProviders(
      <AuthShell title="Sign in">
        <p>form</p>
      </AuthShell>,
    );

    expect(container.querySelector('.auth__lede')).toBeNull();
    expect(container.querySelector('.auth__footer')).toBeNull();
  });
});
