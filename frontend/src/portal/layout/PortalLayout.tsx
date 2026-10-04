/**
 * The portal chrome: a left rail on desktop, a drawer opened from **Menu** on a
 * narrow screen, filtered by the signed-in user's roles and, for Renew, their kind.
 *
 * A reader who has not finished the join wizard (`isOnboarded`) gets neither the
 * rail nor the **Menu** toggle: the wizard is the whole portal until it is done, so
 * the header keeps only **Help**, the reader's name, and **Sign out**.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import type { JSX, RefObject } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';

import { useAuth, useSignOut } from '../auth/useAuth';
import { isOnboarded } from '../features/join/steps';
import { Button } from '../components/Button';
import { GUIDE_PREFIX } from '../guide';
import { helpPath } from '../help';
import type { User } from '../api/types';
import { groupedNavItems } from '../nav';
import { sitePath } from '../urlPrefix';

/** The reader's name for the header, or their address when no name is on file. */
export function headerName(user: Pick<User, 'first_name' | 'last_name' | 'email'>): string {
  return `${user.first_name} ${user.last_name}`.trim() || user.email;
}

/**
 * Keeps the rail's current entry in view, and says whether more entries lie below
 * the rail's visible part.
 *
 * The rail scrolls on its own when the reader's menu is taller than the window: on a
 * desktop always, and on a narrow screen as the open drawer.  On every page, and each
 * time the drawer opens, it is scrolled, by itself alone and never the page, until the
 * current entry shows.  `hasMoreBelow` drives the shadow at its foot.
 */
function useRailScroll(
  pathname: string,
  hasRail: boolean,
  drawerOpen: boolean,
): {
  railRef: RefObject<HTMLElement | null>;
  hasMoreBelow: boolean;
  handleRailScroll: () => void;
} {
  const railRef = useRef<HTMLElement | null>(null);
  const [hasMoreBelow, setHasMoreBelow] = useState(false);

  const handleRailScroll = useCallback(() => {
    const rail = railRef.current;
    if (rail === null) return;
    setHasMoreBelow(rail.scrollTop + rail.clientHeight < rail.scrollHeight - 1);
  }, []);

  useEffect(() => {
    const rail = railRef.current;
    const current = rail?.querySelector<HTMLElement>('.portal__nav-link.is-active');
    if (rail && current) {
      // Where the entry sits inside the rail's scrolled content.
      const top =
        current.getBoundingClientRect().top - rail.getBoundingClientRect().top + rail.scrollTop;
      const bottom = top + current.offsetHeight;
      if (top < rail.scrollTop || bottom > rail.scrollTop + rail.clientHeight) {
        rail.scrollTop = Math.max(0, top - rail.clientHeight / 2);
      }
    }
    handleRailScroll();
  }, [pathname, hasRail, drawerOpen, handleRailScroll]);

  useEffect(() => {
    window.addEventListener('resize', handleRailScroll);
    return () => window.removeEventListener('resize', handleRailScroll);
  }, [handleRailScroll]);

  return { railRef, hasMoreBelow, handleRailScroll };
}

/** The portal chrome: header, role-filtered navigation, and the routed page outlet. */
export function PortalLayout(): JSX.Element {
  const { user, roles, isAuthenticated } = useAuth();
  const { signOut, isPending: isSigningOut } = useSignOut();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement | null>(null);

  // Any navigation closes the mobile drawer and puts the page back at the top:
  // a screen opened from halfway down the last one starts mid-content
  // otherwise, because the browser keeps the scroll position of the document.
  useEffect(() => {
    setDrawerOpen(false);
    window.scrollTo({ top: 0, left: 0 });
  }, [location.pathname]);

  // The drawer opens at the top of the page, under the bar, so a reader who scrolled
  // down before pressing Menu is taken back up to it rather than seeing nothing change.
  useEffect(() => {
    if (drawerOpen) window.scrollTo({ top: 0, left: 0 });
  }, [drawerOpen]);

  // Escape closes an open drawer and hands focus back to the Menu button.
  useEffect(() => {
    if (!drawerOpen) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      setDrawerOpen(false);
      toggleRef.current?.focus();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [drawerOpen]);

  const groups = isOnboarded(user)
    ? groupedNavItems(roles, {
        isEffectiveFriend: user?.membership.status === 'friend',
        isLifetime: user?.membership.is_lifetime === true,
      })
    : [];
  const hasRail = groups.length > 0;
  const { railRef, hasMoreBelow, handleRailScroll } = useRailScroll(
    location.pathname,
    hasRail,
    drawerOpen,
  );

  return (
    <div className="portal" data-drawer-open={drawerOpen ? 'true' : 'false'}>
      <a className="skip-link" href="#portal-main">
        Skip to content
      </a>

      <header className="portal__bar">
        <div className="portal__bar-inner">
          {hasRail ? (
            <button
              ref={toggleRef}
              type="button"
              className="button button--quiet button--small portal__drawer-toggle"
              aria-expanded={drawerOpen}
              aria-controls="portal-nav"
              onClick={() => setDrawerOpen((open) => !open)}
            >
              Menu
            </button>
          ) : null}

          <Link to="/" className="wordmark portal__wordmark">
            Cal<span>DART</span>
            <span className="wordmark__sub">Member portal</span>
          </Link>

          <div className="portal__identity">
            {/* A plain anchor, not `Link`: the guide is outside the SPA, under a
                path the router's basename would otherwise prefix onto. */}
            <a
              href={helpPath(location.pathname)}
              className="button button--quiet button--small portal__help-link"
              target="_blank"
              rel="noopener"
              aria-label="Help for this screen"
            >
              Help
            </a>
            {isAuthenticated && user ? (
              <>
                <span className="muted portal__name" title={user.email}>
                  {headerName(user)}
                </span>
                <Button variant="quiet" small onClick={() => signOut()} disabled={isSigningOut}>
                  Sign out
                </Button>
              </>
            ) : (
              <Link to="/login" className="button button--small">
                Sign in
              </Link>
            )}
          </div>
        </div>
      </header>

      <div className={hasRail ? 'portal__frame' : 'portal__frame portal__frame--no-rail'}>
        {hasRail ? (
          <nav
            ref={railRef}
            className="portal__rail"
            id="portal-nav"
            aria-label="Portal sections"
            data-more-below={hasMoreBelow ? 'true' : 'false'}
            onScroll={handleRailScroll}
          >
            {groups.map((bucket) => (
              <div key={bucket.group} className="portal__nav-group">
                <p className="eyebrow">{bucket.group}</p>
                <ul role="list">
                  {bucket.items.map((item) => (
                    <li key={item.to}>
                      <NavLink
                        to={item.to}
                        end={item.end}
                        className={({ isActive }) =>
                          isActive ? 'portal__nav-link is-active' : 'portal__nav-link'
                        }
                      >
                        {item.label}
                      </NavLink>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            <div className="portal__rail-footer muted">
              <p>
                <a href={GUIDE_PREFIX} target="_blank" rel="noopener">
                  User guide
                </a>
              </p>
              <p>
                <a href={sitePath('/')}>Back to caldart.org</a>
              </p>
            </div>
          </nav>
        ) : null}

        <main className="portal__main" id="portal-main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
