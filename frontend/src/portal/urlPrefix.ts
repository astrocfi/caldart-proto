/**
 * The path prefix the site is served under, and the addresses built from it.
 *
 * Django stamps the prefix on `<html>` as `data-url-prefix` in both of its
 * shells: empty when the site is the root of its host, or a path such as
 * `/caldart-proto` when a web server in front of it serves it under one. It is
 * read once, when this module is first imported. Every real URL the frontend
 * writes itself (a fetch, a plain link, a redirect address handed to a payment
 * provider) goes through `sitePath`; React Router paths are relative to
 * `PORTAL_BASENAME` and need nothing.
 */

/** The prefix, with a leading slash and no trailing one, or the empty string. */
export const URL_PREFIX: string = document.documentElement.dataset.urlPrefix ?? '';

/**
 * The address of `path` on this site: `path` with the prefix in front.
 *
 * @param path a root-relative path, such as `/docs/`.
 * @returns the path the browser requests, such as `/caldart-proto/docs/`.
 */
export function sitePath(path: string): string {
  return `${URL_PREFIX}${path}`;
}

/** Where the REST API lives. */
export const API_BASE: string = sitePath('/api/v1');

/** Where Django mounts the portal SPA: the router's basename. */
export const PORTAL_BASENAME: string = sitePath('/portal');
