import { afterEach, describe, expect, it } from 'vitest';

import { clearUrlPrefix, stampUrlPrefix } from '@test/render';

describe('setupReturnUrl', () => {
  afterEach(clearUrlPrefix);

  it('brings the bank back to the Payments screen, naming the authority', async () => {
    clearUrlPrefix();
    const { setupReturnUrl } = await import('./setupReturn');
    expect(setupReturnUrl('donation')).toBe(
      `${window.location.origin}/portal/payments?mandate=donation`,
    );
  });

  it('brings the bank back under the URL prefix the site is served under', async () => {
    stampUrlPrefix('/x');
    const { setupReturnUrl } = await import('./setupReturn');
    expect(setupReturnUrl('renewal')).toBe(
      `${window.location.origin}/x/portal/payments?mandate=renewal`,
    );
  });
});
