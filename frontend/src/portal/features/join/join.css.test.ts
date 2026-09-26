import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'join.css'), 'utf8');

/** The top-level declaration block for `selector`, ignoring any block nested in a media query. */
function ruleBody(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = new RegExp(`(?:^|\\n)${escaped}\\s*\\{([^}]*)\\}`).exec(css);
  if (!match?.[1]) throw new Error(`no top-level rule found for ${selector}`);
  return match[1];
}

describe('the join shell header and step list', () => {
  // Without this, the header and the step list span the full frame while
  // `.join-card` (46rem, centered) sits underneath, so they look flush left
  // above a centered card on a wide, signed-out screen.
  it.each(['.join-shell .page__header', '.join-shell .join-steps'])(
    "%s keeps the join card's width and centering",
    (selector) => {
      const body = ruleBody(selector);
      expect(body).toContain('max-width: 46rem;');
      expect(body).toContain('margin-inline: auto;');
    },
  );
});
