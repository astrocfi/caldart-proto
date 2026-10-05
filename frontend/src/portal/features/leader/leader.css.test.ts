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

  it('lets the aircraft and its make wrap and give way instead', () => {
    const body = ruleBody('.leader-search__aircraft');
    expect(body).toContain('flex-wrap: wrap;');
    expect(body).toContain('min-width: 0;');
  });

  it('lets the name and the DART give way instead', () => {
    expect(ruleBody('.leader-search__who')).toContain('min-width: 0;');
  });
});

describe('the member check results', () => {
  it('sets the DART under the name on a phone', () => {
    const body = ruleBody('.leader-search__who');
    expect(body).toContain('display: grid;');
    expect(body).toContain('grid-template-columns: minmax(0, 1fr);');
  });

  it('sets the name and the DART in two columns on a wider screen', () => {
    expect(css).toMatch(
      /@media \(min-width: 34rem\) \{\s*\.leader-search__who \{\s*grid-template-columns: minmax\(0, 1fr\) minmax\(0, 1fr\);/,
    );
  });

  it('gives every verdict one width, so the DART column lines up down the list', () => {
    expect(ruleBody('.leader-search__button .leader-search__readiness')).toContain(
      'min-width: 5.5rem;',
    );
  });
});
