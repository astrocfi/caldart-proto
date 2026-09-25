import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'portal.css'), 'utf8');

/** The top-level declaration block for `selector`, ignoring any block nested in a media query. */
function ruleBody(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = new RegExp(`(?:^|\\n)${escaped}\\s*\\{([^}]*)\\}`).exec(css);
  if (!match?.[1]) throw new Error(`no top-level rule found for ${selector}`);
  return match[1];
}

describe('the portal frame width', () => {
  it.each(['.portal__frame', '.portal__bar-inner'])(
    '%s grows with the window instead of capping at --page-max',
    (selector) => {
      const body = ruleBody(selector);
      expect(body).toContain('max-width: none;');
      expect(body).not.toContain('var(--page-max)');
    },
  );

  it('keeps side padding on the frame so content never touches the edge', () => {
    expect(ruleBody('.portal__frame')).toMatch(/padding: 0 var\(--space-4\)/);
  });
});

describe('the frame without a rail', () => {
  it('is a single column', () => {
    expect(ruleBody('.portal__frame--no-rail')).toContain('grid-template-columns: minmax(0, 1fr);');
  });

  it('stays a single column on a wide window', () => {
    // Both rules weigh the same, so the later one wins inside the media query.
    const twoColumns = css.indexOf('grid-template-columns: var(--rail-width) minmax(0, 1fr);');
    expect(twoColumns).toBeGreaterThan(-1);
    expect(css.indexOf('.portal__frame--no-rail')).toBeGreaterThan(twoColumns);
  });
});

describe('the auth card', () => {
  it('takes its width from the auth panel rather than a portal.css rule', () => {
    expect(css).not.toMatch(/\.auth-card\b/);
  });
});

describe('non-report content inside the uncapped frame', () => {
  it('caps a card at the portal working width', () => {
    expect(ruleBody('.portal__main .card')).toContain('max-width: var(--page-max);');
  });

  it('lets a card built around a report table grow with the frame', () => {
    expect(ruleBody('.portal__main .card:has(.data-table)')).toContain('max-width: none;');
  });

  it("caps the dashboard's ratio grid at the portal working width", () => {
    expect(ruleBody('.portal__main .grid')).toContain('max-width: var(--page-max);');
  });
});
