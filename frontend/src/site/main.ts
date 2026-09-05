/**
 * Public-site enhancements (PLAN §7).
 *
 * The Wagtail templates render fine without JavaScript; this only adds the
 * mobile nav toggle and keeps the skip link honest.
 */
import '../styles/index.css';

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

function initSkipLink(): void {
  const link = document.querySelector<HTMLAnchorElement>('.skip-link');
  const target = document.getElementById('main');
  if (!link || !target) return;
  link.addEventListener('click', () => {
    target.setAttribute('tabindex', '-1');
    target.focus({ preventScroll: false });
  });
}

function start(): void {
  initNavToggle();
  initSkipLink();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', start);
} else {
  start();
}
