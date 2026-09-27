import { afterEach, describe, expect, it } from 'vitest';

import { clearUrlPrefix, stampUrlPrefix } from '@test/render';
import { isGuidePath } from './guide';

describe('isGuidePath', () => {
  it('recognizes the guide root and its pages', () => {
    expect(isGuidePath('/docs')).toBe(true);
    expect(isGuidePath('/docs/')).toBe(true);
    expect(isGuidePath('/docs/member/dashboard/')).toBe(true);
  });

  it('leaves portal routes alone', () => {
    expect(isGuidePath('/profile')).toBe(false);
    expect(isGuidePath('/documents/')).toBe(false);
    expect(isGuidePath('/')).toBe(false);
  });
});

describe('the guide under a URL prefix', () => {
  afterEach(clearUrlPrefix);

  it('lives under the prefix', async () => {
    stampUrlPrefix('/x');
    const { GUIDE_PREFIX } = await import('./guide');
    expect(GUIDE_PREFIX).toBe('/x/docs/');
  });

  it('recognizes a guide page under the prefix', async () => {
    stampUrlPrefix('/x');
    const guide = await import('./guide');
    expect(guide.isGuidePath('/x/docs/member/dashboard/')).toBe(true);
  });

  it('recognizes the guide root under the prefix without its slash', async () => {
    stampUrlPrefix('/x');
    const guide = await import('./guide');
    expect(guide.isGuidePath('/x/docs')).toBe(true);
  });

  it('does not read the unprefixed guide path as the guide', async () => {
    stampUrlPrefix('/x');
    const guide = await import('./guide');
    expect(guide.isGuidePath('/docs/member/dashboard/')).toBe(false);
  });
});
