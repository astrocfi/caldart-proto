/**
 * Pure helpers for the public site's progressive enhancement.
 *
 * Kept apart from `main.ts` so they can be unit tested without the module's
 * DOM side effects running on import.
 */

/** The themes shipped in `styles/themes/`, mirroring `THEME_CHOICES` in the CMS. */
export const THEMES = [
  'duty',
  'sierra',
  'pacific',
  'night',
  'squadron',
  'flight-deck',
  'contrail',
  'sectional',
  'tarmac',
  'coastal',
  'slate',
  'meridian',
  'monterey-night',
  'granite',
] as const;
export type Theme = (typeof THEMES)[number];

/** Checks whether `value` is one of the shipped theme names. */
export function isTheme(value: string | null | undefined): value is Theme {
  return typeof value === 'string' && (THEMES as readonly string[]).includes(value);
}

/**
 * Index of the nav entry that is current for `path`, or -1 for none.
 *
 * The longest matching href wins, so `/about/history/` highlights "About Us"
 * and not every entry whose path happens to be a prefix. `/` only ever matches
 * itself, and a match must land on a path segment boundary so `/news` never
 * claims `/newsletter`.
 */
export function currentNavIndex(hrefs: readonly string[], path: string): number {
  const target = path.length > 1 && path.endsWith('/') ? path.slice(0, -1) : path;
  let best = -1;
  let bestLength = 0;

  hrefs.forEach((href, index) => {
    if (!href || href.startsWith('#')) return;
    const normalized = href.length > 1 && href.endsWith('/') ? href.slice(0, -1) : href;
    const matches =
      normalized === '/'
        ? target === '/'
        : target === normalized || target.startsWith(`${normalized}/`);
    if (matches && normalized.length > bestLength) {
      best = index;
      bestLength = normalized.length;
    }
  });

  return best;
}
