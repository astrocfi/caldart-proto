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
    expect(container).toHaveTextContent(/^Verified by Dana Leader on 05\/01\/2026$/);
  });

  it('colors a verified item in the current tone', () => {
    render(<VerifiedMark verification={VERIFIED} />);
    expect(screen.getByText('Verified').closest('[data-tone]')).toHaveAttribute(
      'data-tone',
      'current',
    );
  });

  it('reads Not verified and nothing more', () => {
    const { container } = render(<VerifiedMark verification={UNVERIFIED} />);
    expect(container).toHaveTextContent(/^Not verified$/);
  });

  it('draws a check nobody has made yet in amber, not the alarm red', () => {
    render(<VerifiedMark verification={UNVERIFIED} />);
    expect(screen.getByText('Not verified').closest('[data-tone]')).toHaveAttribute(
      'data-tone',
      'expiring',
    );
  });

  it('reads Not yet verified on the member’s own screens, in amber', () => {
    render(<VerifiedMark verification={UNVERIFIED} pending />);
    expect(screen.getByText('Not yet verified').closest('[data-tone]')).toHaveAttribute(
      'data-tone',
      'expiring',
    );
  });

  it('says Expired beside a lapsed date that somebody verified', () => {
    const { container } = render(<VerifiedMark verification={VERIFIED} expired />);
    expect(container).toHaveTextContent(/^Expired\s*Verified by Dana Leader on 05\/01\/2026$/);
  });

  it('says Expired beside a lapsed date nobody verified', () => {
    const { container } = render(<VerifiedMark verification={UNVERIFIED} expired />);
    expect(container).toHaveTextContent(/^Expired\s*Not verified$/);
  });

  it('draws Expired in the expired tone', () => {
    render(<VerifiedMark verification={VERIFIED} expired />);
    expect(screen.getByText('Expired').closest('[data-tone]')).toHaveAttribute(
      'data-tone',
      'expired',
    );
  });

  it('keeps Verified by wording on the member’s own screens', () => {
    const { container } = render(<VerifiedMark verification={VERIFIED} pending />);
    expect(container).toHaveTextContent(/^Verified by Dana Leader on 05\/01\/2026$/);
  });

  it('leaves out the verifier when the account behind the stamp is gone', () => {
    const { container } = render(
      <VerifiedMark verification={{ ...VERIFIED, verified_by: null }} />,
    );
    expect(container).toHaveTextContent(/^Verified on 05\/01\/2026$/);
  });

  it('reads plain Verified from a summary that carries only the flag', () => {
    const { container } = render(<VerifiedMark verification={{ verified: true }} />);
    expect(container).toHaveTextContent(/^Verified$/);
  });
});
