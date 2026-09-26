import { describe, expect, it } from 'vitest';

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
