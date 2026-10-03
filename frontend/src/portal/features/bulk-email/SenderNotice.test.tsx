import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { LEADER_SENDER, NO_DART_SENDER } from '@test/fixtures/bulkEmail';
import { renderWithProviders } from '@test/render';
import { SenderNotice } from './SenderNotice';

describe('SenderNotice', () => {
  it('says why a DART leader with no DART cannot send', () => {
    renderWithProviders(<SenderNotice sender={NO_DART_SENDER} />);
    expect(screen.getByRole('status')).toHaveTextContent(
      'Your profile names no DART, so there is nobody to send to.',
    );
  });

  it('links to My profile, where the DART is set', () => {
    renderWithProviders(<SenderNotice sender={NO_DART_SENDER} />);
    expect(screen.getByRole('link', { name: 'Open My profile' })).toHaveAttribute(
      'href',
      '/profile',
    );
  });

  it('shows nothing for a sender who can send', () => {
    const { container } = renderWithProviders(<SenderNotice sender={LEADER_SENDER} />);
    expect(container).toBeEmptyDOMElement();
  });
});
