/**
 * The user guide the site serves at `/docs/`.
 *
 * The guide is Sphinx output served by Django, not a portal route, so a link
 * to it is a full-page navigation out of the SPA.
 */

/** Where Django serves the built user guide. */
export const GUIDE_PREFIX = '/docs/';

/** True when `path` is a page of the guide rather than a portal route. */
export function isGuidePath(path: string): boolean {
  return path === GUIDE_PREFIX.slice(0, -1) || path.startsWith(GUIDE_PREFIX);
}

/** Leave the SPA for a guide page: the browser loads it from Django. */
export function openGuide(path: string): void {
  window.location.assign(path);
}
