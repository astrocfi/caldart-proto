import { beforeEach, describe, expect, it } from 'vitest';

import { applyThemePreview, markCurrentNav } from './main';

function navFixture(): HTMLElement {
  document.body.innerHTML = `
    <nav data-site-nav>
      <ul>
        <li><a href="/about/">About Us</a></li>
        <li><a href="/news/" aria-current="page">News</a></li>
      </ul>
      <ul>
        <li><a class="button" href="/portal/join">Join</a></li>
      </ul>
    </nav>
  `;
  return document.querySelector<HTMLElement>('[data-site-nav]')!;
}

const currentLabels = (nav: HTMLElement): string[] =>
  Array.from(nav.querySelectorAll('a[aria-current="page"]')).map((a) => a.textContent ?? '');

describe('markCurrentNav', () => {
  it('moves aria-current onto the entry matching the address bar', () => {
    const nav = navFixture();
    markCurrentNav(nav, '/about/history/');
    expect(currentLabels(nav)).toEqual(['About Us']);
  });

  it('clears aria-current when nothing matches', () => {
    const nav = navFixture();
    markCurrentNav(nav, '/contact/');
    expect(currentLabels(nav)).toEqual([]);
  });

  it('marks the portal actions too', () => {
    const nav = navFixture();
    markCurrentNav(nav, '/portal/join');
    expect(currentLabels(nav)).toEqual(['Join']);
  });
});

describe('applyThemePreview', () => {
  let root: HTMLElement;

  beforeEach(() => {
    root = document.createElement('html');
    root.dataset.theme = 'sierra';
  });

  it('does nothing when the viewer is not an administrator', () => {
    applyThemePreview(root, '?theme=night');
    expect(root.dataset.theme).toBe('sierra');
  });

  it('applies a shipped theme for an administrator', () => {
    root.dataset.themePreview = 'allowed';
    applyThemePreview(root, '?theme=night');
    expect(root.dataset.theme).toBe('night');
  });

  it('ignores a theme that is not shipped', () => {
    root.dataset.themePreview = 'allowed';
    applyThemePreview(root, '?theme=sunset');
    expect(root.dataset.theme).toBe('sierra');
  });

  it('ignores a URL with no theme parameter', () => {
    root.dataset.themePreview = 'allowed';
    applyThemePreview(root, '?page=2');
    expect(root.dataset.theme).toBe('sierra');
  });
});
