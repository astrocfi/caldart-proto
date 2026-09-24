import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { currentNavIndex, isTheme, THEMES } from './nav';

const NAV = ['/about/', '/about/darts/', '/news/', '/donate/', '/portal/join', '/portal/login'];

describe('currentNavIndex', () => {
  it('matches an entry exactly', () => {
    expect(currentNavIndex(NAV, '/news/')).toBe(2);
    expect(currentNavIndex(NAV, '/news')).toBe(2);
  });

  it('marks the section for a page below it', () => {
    expect(currentNavIndex(NAV, '/about/history/')).toBe(0);
  });

  it('prefers the longest match, so a nested index wins over its parent', () => {
    expect(currentNavIndex(NAV, '/about/darts/pao/')).toBe(1);
  });

  it('never matches on a partial path segment', () => {
    expect(currentNavIndex(NAV, '/newsletter/')).toBe(-1);
    expect(currentNavIndex(NAV, '/portal/logout')).toBe(-1);
  });

  it('returns -1 when nothing matches', () => {
    expect(currentNavIndex(NAV, '/contact/')).toBe(-1);
  });

  it('only matches the home entry on the home page', () => {
    const withHome = ['/', ...NAV];
    expect(currentNavIndex(withHome, '/')).toBe(0);
    expect(currentNavIndex(withHome, '/news/')).toBe(3);
  });

  it('ignores empty and fragment-only hrefs', () => {
    expect(currentNavIndex(['', '#main', '/news/'], '/news/')).toBe(2);
  });
});

describe('isTheme', () => {
  it('accepts every shipped theme', () => {
    for (const theme of THEMES) expect(isTheme(theme)).toBe(true);
  });

  it('rejects anything else', () => {
    expect(isTheme('sunset')).toBe(false);
    expect(isTheme(null)).toBe(false);
    expect(isTheme(undefined)).toBe(false);
  });
});

describe('the shipped themes', () => {
  const styles = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'styles');
  const index = readFileSync(join(styles, 'index.css'), 'utf8');
  const read = (theme: string): string =>
    readFileSync(join(styles, 'themes', `${theme}.css`), 'utf8');

  it.each(THEMES)('%s has a stylesheet that declares its own block', (theme) => {
    expect(read(theme)).toContain(`:root[data-theme='${theme}']`);
  });

  it.each(THEMES)('%s is imported by index.css', (theme) => {
    expect(index).toContain(`@import './themes/${theme}.css';`);
  });

  // duty, sierra, pacific and night share one type stack, which `tokens.css`
  // carries as the default; every other theme names all three faces itself.
  const SHARED_TYPE = ['duty', 'sierra', 'pacific', 'night'];

  it.each(THEMES.filter((theme) => !SHARED_TYPE.includes(theme)))(
    '%s names its own display, body and mono faces',
    (theme) => {
      const css = read(theme);
      expect(css).toContain('--font-display:');
      expect(css).toContain('--font-body:');
      expect(css).toContain('--font-mono:');
    },
  );
});
