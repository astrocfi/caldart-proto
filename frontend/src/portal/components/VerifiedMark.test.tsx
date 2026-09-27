import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { VerifiedMark } from './VerifiedMark';

const VERIFIED = {
  verified: true,
  verified_by: 'Dana Leader',
  verified_at: '2026-05-01T16:30:00Z',
};

const UNVERIFIED = { verified: false, verified_by: null, verified_at: null };

describe('VerifiedMark', () => {
  it('reads Verified, by whom, and on which day', () => {
    const { container } = render(<VerifiedMark verification={VERIFIED} />);
    expect(container).toHaveTextContent(/^Verified by Dana Leader on 2026\/05\/01$/);
  });

  it('colors a verified item in the current tone', () => {
    render(<VerifiedMark verification={VERIFIED} />);
    expect(screen.getByText('Verified')).toHaveAttribute('data-tone', 'current');
  });

  it('reads Not verified in the expired tone', () => {
    const { container } = render(<VerifiedMark verification={UNVERIFIED} />);
    expect(screen.getByText('Not verified')).toHaveAttribute('data-tone', 'expired');
    expect(container).toHaveTextContent(/^Not verified$/);
  });

  it('reads Not yet verified on the member’s own screens', () => {
    render(<VerifiedMark verification={UNVERIFIED} pending />);
    expect(screen.getByText('Not yet verified')).toBeInTheDocument();
  });

  it('keeps Verified by wording on the member’s own screens', () => {
    const { container } = render(<VerifiedMark verification={VERIFIED} pending />);
    expect(container).toHaveTextContent(/^Verified by Dana Leader on 2026\/05\/01$/);
  });

  it('leaves out the verifier when the account behind the stamp is gone', () => {
    const { container } = render(
      <VerifiedMark verification={{ ...VERIFIED, verified_by: null }} />,
    );
    expect(container).toHaveTextContent(/^Verified on 2026\/05\/01$/);
  });

  it('reads plain Verified from a summary that carries only the flag', () => {
    const { container } = render(<VerifiedMark verification={{ verified: true }} />);
    expect(container).toHaveTextContent(/^Verified$/);
  });
});
