import type { ReactNode } from 'react';

/**
 * The portal's waiting indicator, announced to screen readers as "Loading".
 *
 * The guards show it while `GET /auth/me` settles, and the router shows it as
 * the root route's hydrate fallback while it resolves the first page a visitor
 * asks for.  A move between screens after that shows it no further: the router
 * holds the current screen until the next page's chunk arrives.
 */
export function Loading(): ReactNode {
  return (
    <div className="portal-loading" role="status" aria-live="polite">
      <span className="visually-hidden">Loading</span>
    </div>
  );
}
