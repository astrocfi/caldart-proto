import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'portal.css'), 'utf8');

/**
 * The top-level declaration block for `selector` in `source` (portal.css by
 * default), ignoring any block nested in a media query.
 */
function ruleBody(selector: string, source: string = css): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = new RegExp(`(?:^|\\n)${escaped}\\s*\\{([^}]*)\\}`).exec(source);
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

describe('the join wizard card', () => {
  const joinCss = readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), 'features/join/join.css'),
    'utf8',
  );

  it('centers itself in the frame', () => {
    expect(ruleBody('.portal__main .card.join-card', joinCss)).toContain('margin-inline: auto;');
  });

  // `.portal__main .card` caps every card at --page-max; the join card's own
  // narrower caps must outweigh it or the account step spreads to 76rem.
  it.each([
    ['.portal__main .card.join-card', '46rem'],
    ['.portal__main .card.join-card--narrow', '30rem'],
  ])('%s keeps its own width inside the portal', (selector, width) => {
    expect(ruleBody(selector, joinCss)).toContain(`max-width: ${width};`);
  });
});

describe('the join shell header and step list', () => {
  const joinCss = readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), 'features/join/join.css'),
    'utf8',
  );

  // Without this, the header and the step list span the full frame while
  // `.join-card` (46rem, centered) sits underneath, so they look flush left
  // above a centered card on a wide, signed-out screen.
  it.each(['.join-shell .page__header', '.join-shell .join-steps'])(
    "%s keeps the join card's width and centering",
    (selector) => {
      const body = ruleBody(selector, joinCss);
      expect(body).toContain('max-width: 46rem;');
      expect(body).toContain('margin-inline: auto;');
    },
  );
});

describe('the auth card', () => {
  const authCss = readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), 'features/auth/auth.css'),
    'utf8',
  );

  it('takes its width from the auth panel rather than a portal.css rule', () => {
    expect(css).not.toMatch(/\.auth-card\b/);
  });

  it.each(['max-width: 26rem;', 'margin-inline: auto;'])(
    'gives the auth panel %s so the card sits centered and narrow',
    (declaration) => {
      expect(ruleBody('.auth__panel', authCss)).toContain(declaration);
    },
  );

  it('pads the auth card more roomily than a plain card', () => {
    expect(ruleBody('.auth-card', authCss)).toContain('padding: var(--space-6);');
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
