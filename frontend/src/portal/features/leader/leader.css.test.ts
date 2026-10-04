import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'leader.css'), 'utf8');

/** The top-level declaration block for `selector` in leader.css. */
function ruleBody(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = new RegExp(`(?:^|\\n)${escaped}\\s*\\{([^}]*)\\}`).exec(css);
  if (!match?.[1]) throw new Error(`no top-level rule found for ${selector}`);
  return match[1];
}

describe('a result row on a phone', () => {
  it('keeps GO or NO-GO on one line', () => {
    expect(ruleBody('.leader-search__readiness')).toContain('white-space: nowrap;');
  });

  it('never squeezes the verdict to make room for the name', () => {
    expect(ruleBody('.leader-search__readiness')).toContain('flex-shrink: 0;');
  });

  it.each(['.leader-search__who', '.leader-search__aircraft'])(
    'lets %s wrap and give way instead',
    (selector) => {
      const body = ruleBody(selector);
      expect(body).toContain('flex-wrap: wrap;');
      expect(body).toContain('min-width: 0;');
    },
  );
});
