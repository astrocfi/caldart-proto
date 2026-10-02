import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@test/render';
import { BouncedChip } from './BouncedChip';

describe('BouncedChip', () => {
  it('reads Bounced and the date the address bounced', () => {
    // Noon UTC is October 1st on every clock from UTC-11 to UTC+11.
    renderWithProviders(<BouncedChip bouncedAt="2026-10-01T12:00:00Z" detail="" />);

    expect(screen.getByText('Bounced 10/01/2026')).toHaveClass('chip--bad');
  });

  it('shows the report detail beside the chip', () => {
    renderWithProviders(
      <BouncedChip bouncedAt="2026-10-01T12:00:00Z" detail="5.1.1 User unknown" />,
    );

    expect(screen.getByText('5.1.1 User unknown')).toBeInTheDocument();
  });

  it('renders nothing for an address with no bounce', () => {
    const { container } = renderWithProviders(<BouncedChip bouncedAt={null} detail="" />);

    expect(container).toBeEmptyDOMElement();
  });
});
