/**
 * Public-site enhancements (PLAN §7).
 *
 * The Wagtail templates render and work with JavaScript switched off; this
 * only adds the mobile nav toggle, keeps the skip link honest, marks the nav
 * entry matching the URL actually in the address bar, and — for website and
 * system administrators — lets `?theme=<slug>` preview a theme before it is
 * saved in Wagtail Site Settings.
 */
// `site.css` pulls in the shared `index.css` itself, so the cascade order is
// fixed by the stylesheet rather than by Vite's chunking.
import '../styles/site.css';
import { currentNavIndex, isTheme } from './nav';

function initNavToggle(): void {
  const toggle = document.querySelector<HTMLButtonElement>('[data-nav-toggle]');
  const nav = document.querySelector<HTMLElement>('[data-site-nav]');
  if (!toggle || !nav) return;

  // Only collapse on small viewports; the CSS shows the nav inline above 48rem.
  const collapse = window.matchMedia('(max-width: 47.99rem)');

  const apply = (): void => {
    if (collapse.matches) {
      nav.hidden = toggle.getAttribute('aria-expanded') !== 'true';
    } else {
      nav.hidden = false;
    }
  };

  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', String(!open));
    apply();
  });

  collapse.addEventListener('change', apply);
  toggle.setAttribute('aria-expanded', 'false');
  apply();
}

/**
 * Re-mark the current nav entry client side.
 *
 * The server already sets `aria-current`, but a cached page or a URL with a
 * query string can leave it on the wrong entry; this settles it against the
 * address bar.
 */
export function markCurrentNav(nav: HTMLElement, path: string): void {
  const links = Array.from(nav.querySelectorAll<HTMLAnchorElement>('a[href]'));
  const index = currentNavIndex(
    links.map((link) => link.getAttribute('href') ?? ''),
    path,
  );
  links.forEach((link, i) => {
    if (i === index) {
      link.setAttribute('aria-current', 'page');
    } else {
      link.removeAttribute('aria-current');
    }
  });
}

function initCurrentPage(): void {
  const nav = document.querySelector<HTMLElement>('[data-site-nav]');
  if (nav) markCurrentNav(nav, window.location.pathname);
}

function initSkipLink(): void {
  const link = document.querySelector<HTMLAnchorElement>('.skip-link');
  const target = document.getElementById('main');
  if (!link || !target) return;
  link.addEventListener('click', () => {
    target.setAttribute('tabindex', '-1');
    target.focus({ preventScroll: false });
  });
}

/**
 * `?theme=night` previews a theme without saving it, for administrators only.
 *
 * The template sets `data-theme-preview="allowed"` on `<html>` when the signed
 * in user holds `website_admin` or `system_admin`, so this cannot be used to
 * deface the site for anybody else — and it changes nothing on the server.
 */
export function applyThemePreview(root: HTMLElement, search: string): void {
  if (root.dataset.themePreview !== 'allowed') return;
  const requested = new URLSearchParams(search).get('theme');
  if (!isTheme(requested)) return;
  root.dataset.theme = requested;
}

function start(): void {
  initNavToggle();
  initCurrentPage();
  initSkipLink();
  applyThemePreview(document.documentElement, window.location.search);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', start);
} else {
  start();
}
