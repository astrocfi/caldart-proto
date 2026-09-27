/** The labeled value a form shows without letting anyone change it. */
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { FixedValue } from './FixedValue';

describe('FixedValue', () => {
  it('names its value with the label, as a group a screen reader announces', () => {
    render(<FixedValue label="Recipient" value="ops@example.test" />);

    expect(screen.getByRole('group', { name: 'Recipient' })).toHaveTextContent('ops@example.test');
  });

  it('offers nothing to edit', () => {
    render(<FixedValue label="Recipient" value="ops@example.test" />);

    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });
});
