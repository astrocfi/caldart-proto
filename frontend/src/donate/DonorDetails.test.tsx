import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@test/render';
import { EMPTY_DONATION_FORM } from './form';
import { DonorDetails } from './DonorDetails';
import type { DonorDetailsProps } from './DonorDetails';

const CONFIG: DonorDetailsProps['config'] = { counties: [], darts: [], states: [] };

function renderDetails(overrides: Partial<DonorDetailsProps> = {}) {
  const handleChange = vi.fn();
  renderWithProviders(
    <DonorDetails
      value={EMPTY_DONATION_FORM}
      onChange={handleChange}
      config={CONFIG}
      {...overrides}
    />,
  );
}

describe('<DonorDetails/>', () => {
  it('shows XXX as the ghost text for Home airport, not a real airport', () => {
    renderDetails();
    expect(screen.getByLabelText('Home airport')).toHaveAttribute('placeholder', 'XXX');
  });
});
