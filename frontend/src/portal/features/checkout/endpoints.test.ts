import { afterEach, describe, expect, it } from 'vitest';

import { clearUrlPrefix, stampUrlPrefix } from '@test/render';

describe('PORTAL_ENDPOINTS.stripeReturnUrl', () => {
  afterEach(clearUrlPrefix);

  it('brings Stripe back to the join wizard on the portal', async () => {
    clearUrlPrefix();
    const { PORTAL_ENDPOINTS } = await import('./endpoints');
    expect(PORTAL_ENDPOINTS.stripeReturnUrl(42)).toBe(
      `${window.location.origin}/portal/join/done?payment_id=42`,
    );
  });

  it('brings Stripe back under the URL prefix the site is served under', async () => {
    stampUrlPrefix('/x');
    const { PORTAL_ENDPOINTS } = await import('./endpoints');
    expect(PORTAL_ENDPOINTS.stripeReturnUrl(42)).toBe(
      `${window.location.origin}/x/portal/join/done?payment_id=42`,
    );
  });
});
