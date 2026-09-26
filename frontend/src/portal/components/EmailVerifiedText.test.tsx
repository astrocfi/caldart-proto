import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { EmailVerifiedText } from './EmailVerifiedText';

describe('EmailVerifiedText', () => {
  it('reads Unverified when the address has not been verified', () => {
    render(<EmailVerifiedText verifiedAt={null} />);
    expect(screen.getByText('Unverified')).toBeInTheDocument();
  });

  it('reads Verified with the date when the address has been verified', () => {
    render(<EmailVerifiedText verifiedAt="2024-07-01T12:05:00Z" />);
    expect(screen.getByText('Verified')).toHaveTextContent('Verified 2024/07/01');
  });
});
