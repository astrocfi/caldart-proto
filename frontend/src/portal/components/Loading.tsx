import type { ReactNode } from 'react';

/**
 * The portal's waiting indicator, announced to screen readers as "Loading".
 *
 * The guards show it while `GET /auth/me` settles, and the router shows it as
 * the root route's hydrate fallback while a page that loads on demand arrives.
 */
export function Loading(): ReactNode {
  return (
    <div className="portal-loading" role="status" aria-live="polite">
      <span className="visually-hidden">Loading</span>
    </div>
  );
}
